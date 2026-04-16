"""Conversation / AI-intake session routes."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.question_engine import QuestionEngine, SessionContext
from app.ai.symptom_extractor import SymptomExtractor
from app.core.config import settings
from app.core.database import get_db
from app.core.security import Role, decrypt_phi, encrypt_phi, get_current_user, require_role
from app.models.ai_report import RedFlagAlert, RedFlagSeverity
from app.models.appointment import Appointment, AppointmentStatus, VisitType as AppointmentVisitType

_extractor = SymptomExtractor()
_engine = QuestionEngine()
_SEVERITY_MAP = {"critical": "emergency", "high": "urgent", "moderate": "elevated"}
from app.models.conversation import (
    ContentType,
    ConversationMessage as ConversationMessageModel,
    ConversationSession,
    MessageRole,
    SessionStatus,
)
from app.schemas.conversation import (
    ConcernRanking,
    ConversationMessage,
    ConversationResponse,
    ConversationStart,
    FollowUpQuestion,
    PatientAnswer,
    TranscriptConfirmation,
    VoiceNoteUpload,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _audit_log(
    db: AsyncSession,
    *,
    user_id: Union[str, uuid.UUID],
    action: str,
    resource_type: str,
    resource_id: Union[str, uuid.UUID],
    success: bool,
) -> None:
    await db.execute(
        text(
            "INSERT INTO audit_logs (id, user_id, action, resource_type, resource_id, success, created_at) "
            "VALUES (:id, :user_id, :action, :resource_type, :resource_id, :success, now())"
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": str(user_id),
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "success": success,
        },
    )


async def _get_session_with_access(
    db: AsyncSession,
    session_id: uuid.UUID,
    current_user: dict,
) -> ConversationSession:
    """Load a conversation session and verify the caller has access.

    Patients may only see their own sessions.  Physicians may see sessions
    belonging to patients assigned to them (including covering-physician
    access).
    """
    result = await db.execute(
        select(ConversationSession)
        .options(selectinload(ConversationSession.messages))
        .where(ConversationSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation session not found",
        )

    user_id = current_user["user_id"]
    role = current_user["role"]

    # Patient sees own session
    if role == Role.PATIENT.value and str(session.patient_id) == str(user_id):
        return session

    # Physician sees sessions tied to their appointments (including unassigned)
    if role == Role.PHYSICIAN.value:
        appt = await db.execute(
            select(Appointment).where(Appointment.id == session.appointment_id)
        )
        appointment = appt.scalar_one_or_none()
        if appointment and (
            appointment.physician_id is None
            or str(appointment.physician_id) == str(user_id)
        ):
            return session

        # Check covering physician access
        covering = await db.execute(
            text(
                "SELECT id FROM physician_coverages "
                "WHERE covering_physician_id = :cov_id "
                "AND absent_physician_id = :abs_id "
                "AND is_active = true "
                "AND start_date <= CURRENT_DATE AND end_date >= CURRENT_DATE"
            ),
            {
                "cov_id": str(user_id),
                "abs_id": str(appointment.physician_id) if appointment else "",
            },
        )
        if covering.first() is not None:
            try:
                await _audit_log(
                    db,
                    user_id=user_id,
                    action="data_access",
                    resource_type="conversation_session",
                    resource_id=session_id,
                    success=True,
                )
            except Exception:
                logger.warning("Failed to write audit log for covering physician access")
            return session

    # Nurse sees sessions for their assigned physician's patients
    if role == Role.NURSE.value:
        appt = await db.execute(
            select(Appointment).where(Appointment.id == session.appointment_id)
        )
        appointment = appt.scalar_one_or_none()
        if appointment:
            return session  # Nurses can access all appointment transcripts

    try:
        await _audit_log(
            db,
            user_id=user_id,
            action="data_access",
            resource_type="conversation_session",
            resource_id=session_id,
            success=False,
        )
    except Exception:
        logger.warning("Failed to write audit log for conversation access denied")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this conversation session",
    )


def _session_to_response(session: ConversationSession) -> ConversationResponse:
    """Map a ConversationSession ORM instance to the response schema."""
    messages = sorted(session.messages, key=lambda m: m.sequence_number)

    def _safe_content(m) -> str:
        """Decrypt patient messages; AI/system messages are stored in plaintext."""
        if m.role == MessageRole.PATIENT:
            try:
                return decrypt_phi(m.content)
            except Exception:
                return m.content
        return m.content

    return ConversationResponse(
        session_id=session.id,
        status=session.status.value,
        messages=[
            ConversationMessage(
                role=m.role.value,
                content=_safe_content(m),
                content_type=m.content_type.value,
            )
            for m in messages
        ],
        questions_asked_count=session.questions_asked_count,
    )


# ---------------------------------------------------------------------------
# Intelligent follow-up question generation
# ---------------------------------------------------------------------------

# Questions organised by clinical domain — each list is asked in order,
# then we move to the next domain.
_DOMAIN_QUESTIONS = {
    "symptom_detail": [
        "When did you first notice this? Was the onset sudden or gradual?",
        "How would you rate the severity on a scale of 1-10?",
        "Is it constant, or does it come and go?",
        "Does anything make it better or worse (movement, rest, medication, position)?",
    ],
    "associated_symptoms": [
        "Have you noticed any other symptoms along with this, such as fever, nausea, or fatigue?",
        "Has this affected your sleep, appetite, or mood?",
    ],
    "medications": [
        "Are you currently taking any medications, vitamins, or supplements?",
        "Have you tried any treatments or medications for this concern?",
    ],
    "medical_history": [
        "Do you have any chronic conditions or past diagnoses I should know about?",
        "Have you had any surgeries or hospitalizations in the past?",
    ],
    "allergies": [
        "Do you have any known allergies to medications, foods, or other substances?",
    ],
    "lifestyle": [
        "Has this issue affected your ability to work, exercise, or perform daily activities?",
    ],
    "family_history": [
        "Is there any family history of similar conditions?",
    ],
}

_DOMAIN_ORDER = [
    "symptom_detail",
    "associated_symptoms",
    "medications",
    "medical_history",
    "allergies",
    "lifestyle",
    "family_history",
]


def _generate_follow_up(
    question_number: int,
    visit_type: str,
    symptoms: list,
    latest_answer: str,
) -> str:
    """Generate a contextual follow-up question based on extracted symptoms."""

    # First question after initial concern — acknowledge what was found
    if question_number == 1 and symptoms:
        names = [s.symptom_name.replace("_", " ") for s in symptoms]
        severity_note = ""
        for s in symptoms:
            if s.severity == "severe":
                severity_note = " I understand this sounds quite serious."
                break
        duration_note = ""
        for s in symptoms:
            if s.duration_mentioned:
                duration_note = f" You mentioned this has been going on {s.duration_mentioned}."
                break
        return (
            f"Thank you for sharing that. I understand you're experiencing "
            f"{', '.join(names)}.{severity_note}{duration_note} "
            f"{_DOMAIN_QUESTIONS['symptom_detail'][0]}"
        )

    # Walk through domains in order based on question number
    q_idx = question_number - 1  # 0-based
    cumulative = 0
    for domain in _DOMAIN_ORDER:
        questions = _DOMAIN_QUESTIONS[domain]
        if q_idx < cumulative + len(questions):
            return questions[q_idx - cumulative]
        cumulative += len(questions)

    # If we've exhausted all domain questions, ask a wrap-up (only once)
    return "__WRAP_UP__"


# ---------------------------------------------------------------------------
# POST /conversations/start
# ---------------------------------------------------------------------------

@router.post("/start", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def start_conversation(
    payload: ConversationStart,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Start a new AI intake conversation session.

    The patient must accept the disclaimer before proceeding.  If no
    pending-intake appointment exists, one is auto-created.
    """
    patient_id = current_user["user_id"]

    # Find the latest pending-intake appointment for this patient
    result = await db.execute(
        select(Appointment)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.status == AppointmentStatus.PENDING_INTAKE,
            Appointment.visit_type == payload.visit_type,
        )
        .order_by(Appointment.created_at.desc())
        .limit(1)
    )
    appointment = result.scalar_one_or_none()

    if appointment is None:
        # Auto-create a pending intake appointment for the patient
        appointment = Appointment(
            patient_id=patient_id,
            visit_type=AppointmentVisitType(payload.visit_type),
            status=AppointmentStatus.PENDING_INTAKE,
        )
        db.add(appointment)
        await db.flush()

    # Check for an existing active session on this appointment — resume it
    existing = await db.execute(
        select(ConversationSession)
        .options(selectinload(ConversationSession.messages))
        .where(
            ConversationSession.appointment_id == appointment.id,
            ConversationSession.status == SessionStatus.IN_PROGRESS,
        )
    )
    existing_session = existing.scalar_one_or_none()
    if existing_session is not None:
        return _session_to_response(existing_session)

    now = datetime.now(timezone.utc)
    session = ConversationSession(
        appointment_id=appointment.id,
        patient_id=patient_id,
        visit_type=payload.visit_type,
        status=SessionStatus.IN_PROGRESS,
        disclaimer_accepted=True,
        disclaimer_accepted_at=now,
        started_at=now,
        last_activity_at=now,
    )
    db.add(session)
    await db.flush()

    # Add the opening system message
    opening_msg = ConversationMessageModel(
        session_id=session.id,
        sequence_number=0,
        role=MessageRole.AI,
        content="Welcome to your intake session. I will ask you a series of questions about your health concerns. Please answer as completely as you can.",
        content_type=ContentType.TEXT,
    )
    db.add(opening_msg)
    await db.flush()

    # Seed chronic conditions into ai_context so the question engine and red-flag
    # checker can cross-reference the patient's medical history during intake.
    chronic_conditions: list[str] = []
    if not settings.EPIC_CLIENT_ID:
        # Demo / sandbox mode — use the mock FHIR chart
        from app.services.epic_fhir import mock_patient_records
        chronic_conditions = [c["code_display"] for c in mock_patient_records()["conditions"]]
    else:
        # Production: load from encrypted PatientProfile if available
        from app.models.patient import PatientProfile
        prof_result = await db.execute(
            select(PatientProfile).where(PatientProfile.user_id == patient_id)
        )
        prof = prof_result.scalar_one_or_none()
        if prof and prof.chronic_conditions:
            try:
                chronic_conditions = json.loads(decrypt_phi(prof.chronic_conditions))
            except Exception:
                logger.warning("Failed to decrypt chronic_conditions for patient %s", patient_id)

    if chronic_conditions:
        # Pre-answer questions that are already resolved by the patient's FHIR
        # medical history so the question engine never asks "do you have
        # diabetes?" when we already know they do from their EHR record.
        pre_answers: dict = {}
        pre_asked: list[str] = []
        for cond in chronic_conditions:
            cond_lower = cond.lower()
            if "diabetes" in cond_lower:
                for qid in ("dn_diabetes_known", "pad_diabetes", "dm_history"):
                    pre_answers[qid] = "yes"
                    pre_asked.append(qid)
            if "hypertension" in cond_lower:
                for qid in ("ht_known",):
                    pre_answers[qid] = "yes"
                    pre_asked.append(qid)
        session.ai_context = {
            "patient_chronic_conditions": chronic_conditions,
            "answers": pre_answers,
            "asked_question_ids": pre_asked,
        }

    try:
        await _audit_log(
            db,
            user_id=patient_id,
            action="data_modify",
            resource_type="conversation_session",
            resource_id=session.id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for start_conversation")

    await db.commit()
    await db.refresh(session, ["messages"])
    return _session_to_response(session)


# ---------------------------------------------------------------------------
# POST /conversations/{session_id}/answer
# ---------------------------------------------------------------------------

@router.post("/{session_id}/answer", response_model=ConversationResponse)
async def submit_answer(
    session_id: uuid.UUID,
    payload: PatientAnswer,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Submit a patient answer to the current question and receive the next.

    Each answer is stored as an encrypted message.  The AI generates a
    follow-up question based on the conversation history so far, up to the
    maximum question limit.
    """
    session = await _get_session_with_access(db, session_id, current_user)

    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation is not in progress",
        )

    if session.questions_asked_count >= session.max_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum number of questions reached. Please complete the conversation.",
        )

    # Record the patient's answer
    next_seq = len(session.messages)
    patient_msg = ConversationMessageModel(
        session_id=session.id,
        sequence_number=next_seq,
        role=MessageRole.PATIENT,
        content=encrypt_phi(payload.answer_text),
        content_type=ContentType.TEXT,
    )
    db.add(patient_msg)

    # ── Generate next AI follow-up question using QuestionEngine ──
    session.questions_asked_count += 1
    session.last_activity_at = datetime.now(timezone.utc)

    # Load accumulated AI context (symptoms, asked question IDs, answers)
    ctx_data: dict = session.ai_context or {}
    all_symptoms: list[str] = list(ctx_data.get("extracted_symptoms", []))
    asked_question_ids: list[str] = list(ctx_data.get("asked_question_ids", []))
    all_answers: dict = dict(ctx_data.get("answers", {}))
    last_question_id: str | None = ctx_data.get("last_question_id")
    chronic_conditions: list[str] = ctx_data.get("patient_chronic_conditions", [])

    # Associate this answer with the last asked question ID
    if last_question_id:
        all_answers[last_question_id] = payload.answer_text

    # Extract symptoms only from the initial complaint (first answer).
    # Follow-up yes/no answers can contain incidental words ("yes, I have some
    # numbness") that the extractor would misread as new chief complaints and
    # open unrelated condition branches (e.g. wrist/carpal-tunnel from "numbness"
    # in a foot-pain session).
    new_symptoms = []
    if session.questions_asked_count <= 1:
        new_symptoms = _extractor.extract(payload.answer_text)
        for sym in new_symptoms:
            if sym.symptom_name not in all_symptoms:
                all_symptoms.append(sym.symptom_name)

    # Red-flag check — inject chronic conditions as context so history-aware
    # patterns (e.g. diabetic foot vascular) can fire correctly
    enriched_answers = dict(all_answers)
    if chronic_conditions:
        enriched_answers["__chronic_conditions__"] = " ".join(chronic_conditions).lower()
    flags = _engine.check_red_flags(all_symptoms, enriched_answers)
    if flags:
        existing_flag_descs: set[str] = set()
        if session.appointment_id:
            flag_result = await db.execute(
                select(RedFlagAlert).where(
                    RedFlagAlert.appointment_id == session.appointment_id,
                    RedFlagAlert.patient_id == session.patient_id,
                )
            )
            existing_flag_descs = {a.trigger_description for a in flag_result.scalars().all()}

        for f in flags:
            if f.trigger_description not in existing_flag_descs:
                sev_str = _SEVERITY_MAP.get(f.severity, "elevated")
                if session.appointment_id:
                    appt_result = await db.execute(
                        select(Appointment).where(Appointment.id == session.appointment_id)
                    )
                    appt = appt_result.scalar_one_or_none()
                    if appt:
                        alert = RedFlagAlert(
                            appointment_id=session.appointment_id,
                            patient_id=session.patient_id,
                            physician_id=appt.physician_id,  # may be None for unassigned appts
                            trigger_description=f.trigger_description,
                            severity=RedFlagSeverity(sev_str),
                            session_was_completed=False,
                        )
                        db.add(alert)
                        logger.warning(
                            "red flag detected | session=%s flag=%s severity=%s",
                            session.id, f.trigger_description, sev_str,
                        )

    # Select next question using QuestionEngine
    qctx = SessionContext(
        extracted_symptoms=all_symptoms,
        previous_questions=asked_question_ids,
        previous_answers=all_answers,
        patient_medical_history={"chronic_conditions": chronic_conditions},
        total_questions_asked=session.questions_asked_count,
    )
    next_q = _engine.select_next_question(qctx)

    new_last_question_id: str | None = None
    if next_q is not None:
        asked_question_ids.append(next_q.question_id)
        new_last_question_id = next_q.question_id
        ai_question_text = next_q.text
    else:
        # No more condition-specific questions — fall back to domain questions
        follow_up = _generate_follow_up(
            question_number=session.questions_asked_count,
            visit_type=session.visit_type,
            symptoms=new_symptoms,
            latest_answer=payload.answer_text,
        )
        if follow_up == "__WRAP_UP__":
            prev_ai_msgs = [m for m in session.messages if m.role == MessageRole.AI]
            last_ai = prev_ai_msgs[-1].content if prev_ai_msgs else ""
            if "anything else" in last_ai.lower():
                ai_question_text = (
                    "Thank you for completing the intake questionnaire! Your responses "
                    "have been recorded and will help your physician prepare for your "
                    "appointment. You can now click 'Finish & Review' to review your "
                    "answers before submitting."
                )
            else:
                ai_question_text = (
                    "Thank you for all that information. Is there anything else about "
                    "your health that you'd like your physician to know about before "
                    "your appointment?"
                )
        else:
            ai_question_text = follow_up

    # Save updated AI context (preserve chronic conditions across turns)
    session.ai_context = {
        "extracted_symptoms": all_symptoms,
        "asked_question_ids": asked_question_ids,
        "answers": all_answers,
        "last_question_id": new_last_question_id,
        "patient_chronic_conditions": chronic_conditions,
    }

    ai_msg = ConversationMessageModel(
        session_id=session.id,
        sequence_number=next_seq + 1,
        role=MessageRole.AI,
        content=ai_question_text,
        content_type=ContentType.TEXT,
    )
    db.add(ai_msg)
    await db.flush()

    try:
        await _audit_log(
            db,
            user_id=current_user["user_id"],
            action="data_modify",
            resource_type="conversation_session",
            resource_id=session_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for submit_answer")

    await db.commit()
    await db.refresh(session, ["messages"])
    return _session_to_response(session)


# ---------------------------------------------------------------------------
# POST /conversations/{session_id}/voice-note
# ---------------------------------------------------------------------------

@router.post("/{session_id}/voice-note")
async def upload_voice_note(
    session_id: uuid.UUID,
    file: UploadFile,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Upload a voice note for AI transcription.

    This is a stub endpoint.  In production it would forward the audio to
    the transcription service, return a preliminary transcript, and await
    patient confirmation via the confirm-transcript endpoint.
    """
    session = await _get_session_with_access(db, session_id, current_user)

    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation is not in progress",
        )

    # Validate file type
    allowed_types = {"audio/wav", "audio/mpeg", "audio/ogg", "audio/webm", "audio/mp4"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format: {file.content_type}",
        )

    # Read file content (in production, stream to transcription service)
    audio_bytes = await file.read()
    if len(audio_bytes) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Voice note exceeds maximum size of 10 MB",
        )

    # Stub transcription result
    preliminary_transcript = (
        "This is a stub transcription of the patient's voice note. "
        "In production, this would come from the transcription service."
    )

    try:
        await _audit_log(
            db,
            user_id=current_user["user_id"],
            action="data_modify",
            resource_type="conversation_session",
            resource_id=session_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for upload_voice_note")
    await db.commit()

    return {
        "session_id": str(session_id),
        "preliminary_transcript": preliminary_transcript,
        "requires_confirmation": True,
    }


# ---------------------------------------------------------------------------
# POST /conversations/{session_id}/confirm-transcript
# ---------------------------------------------------------------------------

@router.post("/{session_id}/confirm-transcript", response_model=ConversationResponse)
async def confirm_transcript(
    session_id: uuid.UUID,
    payload: TranscriptConfirmation,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Confirm or correct a voice-note transcript.

    Once confirmed, the transcript text is stored as a conversation message
    of type voice_transcript.
    """
    session = await _get_session_with_access(db, session_id, current_user)

    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation is not in progress",
        )

    if not payload.confirmed:
        return _session_to_response(session)

    next_seq = len(session.messages)
    voice_msg = ConversationMessageModel(
        session_id=session.id,
        sequence_number=next_seq,
        role=MessageRole.PATIENT,
        content=encrypt_phi(payload.transcript_text),
        content_type=ContentType.VOICE_TRANSCRIPT,
        voice_note_retained=False,
    )
    db.add(voice_msg)

    session.last_activity_at = datetime.now(timezone.utc)
    await db.flush()

    try:
        await _audit_log(
            db,
            user_id=current_user["user_id"],
            action="data_modify",
            resource_type="conversation_session",
            resource_id=session_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for confirm_transcript")

    await db.commit()
    await db.refresh(session, ["messages"])
    return _session_to_response(session)


# ---------------------------------------------------------------------------
# POST /conversations/{session_id}/rank-concerns
# ---------------------------------------------------------------------------

@router.post("/{session_id}/rank-concerns", response_model=ConversationResponse)
async def rank_concerns(
    session_id: uuid.UUID,
    payload: ConcernRanking,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Submit the patient's ranked health concerns (maximum 3).

    This is typically called near the end of the intake flow so the
    physician can see prioritized concerns.
    """
    session = await _get_session_with_access(db, session_id, current_user)

    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation is not in progress",
        )

    session.concerns_ranked = [c.model_dump() for c in payload.concerns]
    session.last_activity_at = datetime.now(timezone.utc)
    await db.flush()

    try:
        await _audit_log(
            db,
            user_id=current_user["user_id"],
            action="data_modify",
            resource_type="conversation_session",
            resource_id=session_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for rank_concerns")

    await db.commit()
    await db.refresh(session, ["messages"])
    return _session_to_response(session)


# ---------------------------------------------------------------------------
# GET /conversations/{session_id}
# ---------------------------------------------------------------------------

@router.get("/{session_id}", response_model=ConversationResponse)
async def get_conversation(
    session_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the current state of a conversation session.

    Patients see their own sessions.  Physicians see sessions for patients
    assigned to them (including covering-physician access).
    """
    session = await _get_session_with_access(db, session_id, current_user)

    try:
        await _audit_log(
            db,
            user_id=current_user["user_id"],
            action="data_access",
            resource_type="conversation_session",
            resource_id=session_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for get_conversation")
    await db.commit()

    return _session_to_response(session)


# ---------------------------------------------------------------------------
# GET /conversations/by-appointment/{appointment_id}
# ---------------------------------------------------------------------------

@router.get("/by-appointment/{appointment_id}", response_model=ConversationResponse)
async def get_conversation_by_appointment(
    appointment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the conversation transcript for an appointment.

    Accessible by the patient (own appointment), assigned/covering physician,
    nurses assigned to the physician, schedulers, and admins.
    """
    # Find the most recent completed session for this appointment
    result = await db.execute(
        select(ConversationSession)
        .options(selectinload(ConversationSession.messages))
        .where(ConversationSession.appointment_id == appointment_id)
        .order_by(ConversationSession.created_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No conversation found for this appointment",
        )

    # Verify access using the existing helper
    await _get_session_with_access(db, session.id, current_user)

    try:
        await _audit_log(
            db,
            user_id=current_user["user_id"],
            action="data_access",
            resource_type="conversation_session",
            resource_id=session.id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for get_conversation_by_appointment")
    await db.commit()

    return _session_to_response(session)


# ---------------------------------------------------------------------------
# PUT /conversations/{session_id}/update
# ---------------------------------------------------------------------------

@router.put("/{session_id}/update", response_model=ConversationResponse)
async def update_conversation(
    session_id: uuid.UUID,
    payload: PatientAnswer,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Update a previous response in the conversation before the appointment.

    Creates a versioned update: the original message is preserved and a new
    message is appended with the revised answer.  This allows physicians to
    see the change history.
    """
    session = await _get_session_with_access(db, session_id, current_user)

    if session.status == SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a completed conversation",
        )

    # Find the message being updated
    target_msg = None
    for msg in session.messages:
        if msg.sequence_number == payload.question_sequence and msg.role == MessageRole.PATIENT:
            target_msg = msg
            break

    if target_msg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original answer not found at the specified sequence number",
        )

    # Create a versioned update as a new message referencing the original sequence
    next_seq = len(session.messages)
    update_msg = ConversationMessageModel(
        session_id=session.id,
        sequence_number=next_seq,
        role=MessageRole.PATIENT,
        content=encrypt_phi(payload.answer_text),
        content_type=ContentType.TEXT,
    )
    db.add(update_msg)

    # Bump the appointment version
    appt_result = await db.execute(
        select(Appointment).where(Appointment.id == session.appointment_id)
    )
    appointment = appt_result.scalar_one_or_none()
    if appointment:
        appointment.version += 1
        await db.execute(
            text(
                "INSERT INTO appointment_versions (id, appointment_id, version_number, changes_json, changed_by, changed_at) "
                "VALUES (:id, :appt_id, :ver, :changes, :user_id, now())"
            ),
            {
                "id": str(uuid.uuid4()),
                "appt_id": str(appointment.id),
                "ver": appointment.version,
                "changes": json.dumps({"type": "conversation_update", "sequence": payload.question_sequence}),
                "user_id": str(current_user["user_id"]),
            },
        )

    session.last_activity_at = datetime.now(timezone.utc)
    await db.flush()

    try:
        await _audit_log(
            db,
            user_id=current_user["user_id"],
            action="data_modify",
            resource_type="conversation_session",
            resource_id=session_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for update_conversation")

    await db.commit()
    await db.refresh(session, ["messages"])
    return _session_to_response(session)


# ---------------------------------------------------------------------------
# POST /conversations/{session_id}/complete
# ---------------------------------------------------------------------------

@router.post("/{session_id}/complete", response_model=ConversationResponse)
async def complete_conversation(
    session_id: uuid.UUID,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Finalize a conversation session and trigger AI report generation.

    Marks the session as completed, updates the appointment status to
    intake_complete, and queues the AI report generation task.
    """
    session = await _get_session_with_access(db, session_id, current_user)

    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation is not in progress",
        )

    if session.questions_asked_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one question must be answered before completing the session",
        )

    now = datetime.now(timezone.utc)
    session.status = SessionStatus.COMPLETED
    session.completed_at = now
    session.last_activity_at = now

    # ── Analyse the conversation for duration estimation ──
    # Use accumulated ai_context (condition ranking + answers) for a smarter estimate
    ctx_data: dict = session.ai_context or {}
    all_symptoms: list[str] = list(ctx_data.get("extracted_symptoms", []))
    all_answers: dict = dict(ctx_data.get("answers", {}))

    # Also extract from full text to catch anything said before context was tracked
    all_patient_text = []
    for m in session.messages:
        if m.role == MessageRole.PATIENT:
            try:
                all_patient_text.append(decrypt_phi(m.content))
            except Exception:
                all_patient_text.append(m.content)
    full_text = " ".join(all_patient_text)
    for sym in _extractor.extract(full_text):
        if sym.symptom_name not in all_symptoms:
            all_symptoms.append(sym.symptom_name)

    # Rank conditions using everything we know
    qctx = SessionContext(
        extracted_symptoms=all_symptoms,
        previous_questions=ctx_data.get("asked_question_ids", []),
        previous_answers=all_answers,
    )
    condition_scores = _engine._rank_conditions(qctx)
    top_condition = condition_scores[0][0] if condition_scores else None

    # Base duration by condition — derived from typical primary-care visit lengths
    _CONDITION_DURATIONS: dict[str, int] = {
        "major_depressive_disorder": 40,
        "generalized_anxiety_disorder": 35,
        "panic_disorder": 30,
        "bipolar_disorder": 50,
        "ptsd": 45,
        "adjustment_disorder": 30,
        "herniated_disc": 30,
        "sciatica": 30,
        "spinal_stenosis": 35,
        "lumbar_strain": 20,
        "cervical_strain": 20,
        "osteoarthritis": 25,
        "rheumatoid_arthritis": 35,
        "fibromyalgia": 40,
        "angina_pectoris": 40,
        "acute_coronary_syndrome": 60,
        "atrial_fibrillation": 40,
        "heart_failure": 50,
        "pulmonary_embolism": 60,
        "asthma": 25,
        "copd_exacerbation": 35,
        "pneumonia": 30,
        "diabetes_mellitus": 30,
        "hypothyroidism": 25,
        "hyperthyroidism": 25,
        "hypertension": 20,
        "urinary_tract_infection": 15,
        "upper_respiratory_infection": 15,
        "migraine": 25,
        "tension_headache": 20,
        "sleep_apnea": 30,
        "insomnia": 25,
        "irritable_bowel_syndrome": 25,
        "gastroesophageal_reflux": 20,
    }

    if session.visit_type == "yearly_checkup":
        base_minutes = 40  # annual physicals are always longer
    elif top_condition:
        base_minutes = _CONDITION_DURATIONS.get(top_condition, 20)
    else:
        base_minutes = 20

    # Adjust for number of distinct symptom clusters (comorbidities)
    extra_symptoms = max(0, len(all_symptoms) - 1)
    base_minutes += extra_symptoms * 5

    # Adjust for positive answers to serious questions (each "yes" = more to discuss)
    yes_count = sum(
        1 for v in all_answers.values()
        if v is True or (isinstance(v, str) and v.strip().lower() in ("yes", "y"))
    )
    base_minutes += yes_count * 2

    # Check for any red flags detected during the session
    flags = _engine.check_red_flags(all_symptoms, all_answers)
    if flags:
        base_minutes += 15  # urgent/complex cases need more time

    suggested = max(15, min(round(base_minutes / 5) * 5, 90))

    # Confidence based on depth of conversation (questions asked + symptom coverage)
    questions_ratio = session.questions_asked_count / max(session.max_questions, 1)
    symptom_count = len(all_symptoms)
    confidence = round(0.55 + (questions_ratio * 0.25) + (min(symptom_count, 3) * 0.06), 2)
    confidence = min(confidence, 0.95)

    range_spread = 5 if questions_ratio > 0.5 else 10
    range_min = max(15, suggested - range_spread)
    range_max = min(90, suggested + range_spread)

    # Build a summary
    symptom_names = [s.replace("_", " ") for s in all_symptoms]
    summary_parts = []
    if symptom_names:
        summary_parts.append(f"Symptoms: {', '.join(symptom_names)}.")
    if top_condition:
        summary_parts.append(f"Primary concern: {top_condition.replace('_', ' ')}.")
    if flags:
        summary_parts.append(f"{len(flags)} red flag(s) identified.")
    summary_parts.append(f"Estimated duration: {suggested} minutes.")
    ai_summary = " ".join(summary_parts) if summary_parts else "Standard visit."

    extracted = _extractor.extract(full_text)  # kept for downstream compatibility

    # Update the appointment status and AI fields
    appt_result = await db.execute(
        select(Appointment).where(Appointment.id == session.appointment_id)
    )
    appointment = appt_result.scalar_one_or_none()
    if appointment:
        appointment.status = AppointmentStatus.INTAKE_COMPLETE
        appointment.ai_suggested_duration = suggested
        appointment.ai_confidence = confidence
        appointment.ai_duration_range_min = range_min
        appointment.ai_duration_range_max = range_max

    # Build red flag JSON for the report
    red_flags_data = []
    for f in flags:
        sev = _SEVERITY_MAP.get(f.severity, "elevated")
        red_flags_data.append({
            "id": str(uuid.uuid4()),
            "trigger_description": f.trigger_description,
            "severity": sev,
            "acknowledged": False,
            "session_completed": True,
            "created_at": now.isoformat(),
        })

    # Create AI report
    try:
        from app.models.ai_report import AIReport
        report = AIReport(
            appointment_id=session.appointment_id,
            session_id=session.id,
            summary=ai_summary,
            suggested_duration=suggested,
            confidence_level=confidence,
            duration_range_min=range_min,
            duration_range_max=range_max,
            red_flags=red_flags_data if red_flags_data else None,
        )
        db.add(report)
        await db.flush()
    except Exception:
        logger.warning("Failed to create AI report stub — table may not exist yet")

    try:
        await _audit_log(
            db,
            user_id=current_user["user_id"],
            action="data_modify",
            resource_type="conversation_session",
            resource_id=session_id,
            success=True,
        )
    except Exception:
        logger.warning("Failed to write audit log for complete_conversation")

    logger.info(
        "Conversation %s completed; AI report generation triggered for appointment %s",
        session_id,
        session.appointment_id,
    )

    await db.commit()
    await db.refresh(session, ["messages"])
    return _session_to_response(session)

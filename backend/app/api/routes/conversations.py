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

from app.ai.symptom_extractor import SymptomExtractor
from app.core.database import get_db
from app.core.security import Role, decrypt_phi, encrypt_phi, get_current_user, require_role
from app.models.appointment import Appointment, AppointmentStatus, VisitType as AppointmentVisitType

_extractor = SymptomExtractor()
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

    # Physician sees sessions tied to their appointments
    if role == Role.PHYSICIAN.value:
        appt = await db.execute(
            select(Appointment).where(Appointment.id == session.appointment_id)
        )
        appointment = appt.scalar_one_or_none()
        if appointment and str(appointment.physician_id) == str(user_id):
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
            # Check nurse-physician assignment (simplified: nurse linked via user table or config)
            nurse_assignment = await db.execute(
                text(
                    "SELECT id FROM nurse_physician_assignments "
                    "WHERE nurse_id = :nurse_id AND physician_id = :phys_id AND is_active = true"
                ),
                {"nurse_id": str(user_id), "phys_id": str(appointment.physician_id)},
            )
            if nurse_assignment.first() is not None:
                return session

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

    # ── Generate next AI follow-up question using symptom extraction ──
    session.questions_asked_count += 1
    session.last_activity_at = datetime.now(timezone.utc)

    # Collect all patient answers so far (decrypted) for symptom analysis
    all_patient_text = []
    for m in session.messages:
        if m.role == MessageRole.PATIENT:
            try:
                all_patient_text.append(decrypt_phi(m.content))
            except Exception:
                all_patient_text.append(m.content)
    all_patient_text.append(payload.answer_text)

    # Extract symptoms from the full conversation
    all_text = " ".join(all_patient_text)
    extracted = _extractor.extract(all_text)
    symptom_names = [s.symptom_name.replace("_", " ") for s in extracted]

    ai_question_text = _generate_follow_up(
        question_number=session.questions_asked_count,
        visit_type=session.visit_type,
        symptoms=extracted,
        latest_answer=payload.answer_text,
    )

    # Check if we've reached the wrap-up phase
    if ai_question_text == "__WRAP_UP__":
        # Check if the previous AI message was already the wrap-up question
        prev_ai_msgs = [m for m in session.messages if m.role == MessageRole.AI]
        last_ai = prev_ai_msgs[-1].content if prev_ai_msgs else ""
        already_asked_wrapup = "anything else" in last_ai.lower()

        if already_asked_wrapup:
            # Patient answered the wrap-up — send a closing message
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
    all_patient_text = []
    for m in session.messages:
        if m.role == MessageRole.PATIENT:
            try:
                all_patient_text.append(decrypt_phi(m.content))
            except Exception:
                all_patient_text.append(m.content)

    full_text = " ".join(all_patient_text)
    extracted = _extractor.extract(full_text)

    # Duration estimation based on symptom count, severity, and visit type
    base_minutes = 15 if session.visit_type == "yearly_checkup" else 20
    symptom_count = len(extracted)
    severe_count = sum(1 for s in extracted if s.severity == "severe")
    moderate_count = sum(1 for s in extracted if s.severity == "moderate")

    suggested = base_minutes + (symptom_count * 3) + (severe_count * 7) + (moderate_count * 3)
    suggested = max(15, min(suggested, 90))  # clamp 15-90 min

    # Confidence based on how much info we gathered
    questions_ratio = session.questions_asked_count / max(session.max_questions, 1)
    confidence = round(0.5 + (questions_ratio * 0.3) + (min(symptom_count, 3) * 0.07), 2)
    confidence = min(confidence, 0.95)

    range_min = max(15, suggested - 10)
    range_max = min(90, suggested + 10)

    # Build a summary from extracted symptoms
    symptom_names = [s.symptom_name.replace("_", " ") for s in extracted]
    summary_parts = []
    if symptom_names:
        summary_parts.append(f"Symptoms: {', '.join(symptom_names)}.")
    if severe_count:
        summary_parts.append(f"{severe_count} severe symptom(s) identified.")
    summary_parts.append(f"Estimated duration: {suggested} minutes.")
    ai_summary = " ".join(summary_parts) if summary_parts else "Standard visit."

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

    # Create AI report stub
    try:
        from app.models.ai_report import AIReport
        report = AIReport(
            appointment_id=session.appointment_id,
            session_id=session.id,
            summary=ai_summary,
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

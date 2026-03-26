"""Conversation / AI-intake session routes."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import Role, encrypt_phi, get_current_user, require_role
from app.models.appointment import Appointment
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
    user_id: str | uuid.UUID,
    action: str,
    resource_type: str,
    resource_id: str | uuid.UUID,
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
            await _audit_log(
                db,
                user_id=user_id,
                action="covering_physician_access_conversation",
                resource_type="conversation_session",
                resource_id=session_id,
                success=True,
            )
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

    await _audit_log(
        db,
        user_id=user_id,
        action="conversation_access_denied",
        resource_type="conversation_session",
        resource_id=session_id,
        success=False,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this conversation session",
    )


def _session_to_response(session: ConversationSession) -> ConversationResponse:
    """Map a ConversationSession ORM instance to the response schema."""
    messages = sorted(session.messages, key=lambda m: m.sequence_number)
    return ConversationResponse(
        session_id=session.id,
        status=session.status.value,
        messages=[
            ConversationMessage(
                role=m.role.value,
                content=m.content,
                content_type=m.content_type.value,
            )
            for m in messages
        ],
        questions_asked_count=session.questions_asked_count,
    )


# ---------------------------------------------------------------------------
# POST /conversations/start
# ---------------------------------------------------------------------------

@router.post("/start", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def start_conversation(
    body: ConversationStart,
    current_user: dict = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Start a new AI intake conversation session.

    The patient must accept the disclaimer before proceeding.  A pending
    appointment for the patient is required; if none exists, the request
    is rejected.
    """
    patient_id = current_user["user_id"]

    # Find the latest pending-intake appointment for this patient
    result = await db.execute(
        select(Appointment)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.status == "pending_intake",
            Appointment.visit_type == body.visit_type,
        )
        .order_by(Appointment.created_at.desc())
        .limit(1)
    )
    appointment = result.scalar_one_or_none()

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending intake appointment found for this visit type",
        )

    # Check for an existing active session on this appointment
    existing = await db.execute(
        select(ConversationSession).where(
            ConversationSession.appointment_id == appointment.id,
            ConversationSession.status == SessionStatus.IN_PROGRESS,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active conversation session already exists for this appointment",
        )

    now = datetime.now(timezone.utc)
    session = ConversationSession(
        appointment_id=appointment.id,
        patient_id=patient_id,
        visit_type=body.visit_type,
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

    await _audit_log(
        db,
        user_id=patient_id,
        action="start_conversation",
        resource_type="conversation_session",
        resource_id=session.id,
        success=True,
    )

    await db.refresh(session, ["messages"])
    return _session_to_response(session)


# ---------------------------------------------------------------------------
# POST /conversations/{session_id}/answer
# ---------------------------------------------------------------------------

@router.post("/{session_id}/answer", response_model=ConversationResponse)
async def submit_answer(
    session_id: uuid.UUID,
    body: PatientAnswer,
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
        content=encrypt_phi(body.answer_text),
        content_type=ContentType.TEXT,
    )
    db.add(patient_msg)

    # Generate next AI follow-up question (placeholder for real AI service call)
    session.questions_asked_count += 1
    session.last_activity_at = datetime.now(timezone.utc)

    ai_question_text = (
        f"Thank you. Follow-up question #{session.questions_asked_count}: "
        "Could you tell me more about when this started and how it affects your daily activities?"
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

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="submit_answer",
        resource_type="conversation_session",
        resource_id=session_id,
        success=True,
    )

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

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="upload_voice_note",
        resource_type="conversation_session",
        resource_id=session_id,
        success=True,
    )

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
    body: TranscriptConfirmation,
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

    if not body.confirmed:
        return _session_to_response(session)

    next_seq = len(session.messages)
    voice_msg = ConversationMessageModel(
        session_id=session.id,
        sequence_number=next_seq,
        role=MessageRole.PATIENT,
        content=encrypt_phi(body.transcript_text),
        content_type=ContentType.VOICE_TRANSCRIPT,
        voice_note_retained=False,
    )
    db.add(voice_msg)

    session.last_activity_at = datetime.now(timezone.utc)
    await db.flush()

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="confirm_transcript",
        resource_type="conversation_session",
        resource_id=session_id,
        success=True,
    )

    await db.refresh(session, ["messages"])
    return _session_to_response(session)


# ---------------------------------------------------------------------------
# POST /conversations/{session_id}/rank-concerns
# ---------------------------------------------------------------------------

@router.post("/{session_id}/rank-concerns", response_model=ConversationResponse)
async def rank_concerns(
    session_id: uuid.UUID,
    body: ConcernRanking,
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

    session.concerns_ranked = [c.model_dump() for c in body.concerns]
    session.last_activity_at = datetime.now(timezone.utc)
    await db.flush()

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="rank_concerns",
        resource_type="conversation_session",
        resource_id=session_id,
        success=True,
    )

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

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="read_conversation",
        resource_type="conversation_session",
        resource_id=session_id,
        success=True,
    )

    return _session_to_response(session)


# ---------------------------------------------------------------------------
# PUT /conversations/{session_id}/update
# ---------------------------------------------------------------------------

@router.put("/{session_id}/update", response_model=ConversationResponse)
async def update_conversation(
    session_id: uuid.UUID,
    body: PatientAnswer,
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
        if msg.sequence_number == body.question_sequence and msg.role == MessageRole.PATIENT:
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
        content=encrypt_phi(body.answer_text),
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
                "changes": '{"type": "conversation_update", "sequence": ' + str(body.question_sequence) + '}',
                "user_id": str(current_user["user_id"]),
            },
        )

    session.last_activity_at = datetime.now(timezone.utc)
    await db.flush()

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="update_conversation_response",
        resource_type="conversation_session",
        resource_id=session_id,
        success=True,
    )

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

    # Update the appointment status
    appt_result = await db.execute(
        select(Appointment).where(Appointment.id == session.appointment_id)
    )
    appointment = appt_result.scalar_one_or_none()
    if appointment:
        appointment.status = "intake_complete"

    # Trigger AI report generation (placeholder -- in production this would
    # enqueue a background task via Celery, ARQ, or similar)
    await db.execute(
        text(
            "INSERT INTO ai_reports "
            "(id, appointment_id, session_id, status, created_at) "
            "VALUES (:id, :appt_id, :sess_id, 'pending', now())"
        ),
        {
            "id": str(uuid.uuid4()),
            "appt_id": str(session.appointment_id),
            "sess_id": str(session.id),
        },
    )

    await db.flush()

    await _audit_log(
        db,
        user_id=current_user["user_id"],
        action="complete_conversation",
        resource_type="conversation_session",
        resource_id=session_id,
        success=True,
    )

    logger.info(
        "Conversation %s completed; AI report generation triggered for appointment %s",
        session_id,
        session.appointment_id,
    )

    await db.refresh(session, ["messages"])
    return _session_to_response(session)

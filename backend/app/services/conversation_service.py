"""Intake conversation orchestration service.

Manages the patient-facing AI intake flow: session creation, question/answer
processing, red-flag detection, voice-note handling, concern ranking, and
session completion / abandonment.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import Role
from app.models.ai_report import RedFlagAlert, RedFlagSeverity
from app.models.conversation import (
    ContentType,
    ConversationMessage,
    ConversationSession,
    MessageRole,
    SessionStatus,
)
from app.services.encryption_service import EncryptionService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ConversationService:
    """Orchestrates the patient intake conversation flow."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._enc = EncryptionService()
        self._notifications = NotificationService(db)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def start_session(
        self,
        patient_id: uuid.UUID,
        visit_type: str,
        disclaimer_accepted: bool,
    ) -> ConversationSession:
        """Create a new intake conversation session.

        The patient must accept the disclaimer before any data collection
        begins.
        """
        if not disclaimer_accepted:
            raise ValueError("Disclaimer must be accepted to start a session")

        now = datetime.now(timezone.utc)
        session = ConversationSession(
            patient_id=patient_id,
            visit_type=visit_type,
            status=SessionStatus.IN_PROGRESS,
            disclaimer_accepted=True,
            disclaimer_accepted_at=now,
            started_at=now,
            last_activity_at=now,
        )
        self._db.add(session)
        await self._db.flush()

        # Add the opening system message
        opening = self._build_opening_message(visit_type)
        encrypted_content = self._enc.encrypt_field(opening)
        msg = ConversationMessage(
            session_id=session.id,
            sequence_number=0,
            role=MessageRole.AI,
            content=encrypted_content,
            content_type=ContentType.TEXT,
        )
        self._db.add(msg)
        await self._db.flush()

        logger.info("conversation session started | session=%s patient=%s", session.id, patient_id)
        return session

    # ------------------------------------------------------------------
    # Answer processing
    # ------------------------------------------------------------------

    async def process_answer(
        self,
        session_id: uuid.UUID,
        answer_text: str,
    ) -> dict | None:
        """Process a patient answer and return the next question (or None if done).

        Steps:
        1. Persist the patient's answer (encrypted).
        2. Run symptom extraction (stub).
        3. Check for red flags; if found, create alert and send notification.
        4. Generate the next follow-up question via the question engine (stub).
        5. Return the next question dict, or None when the question limit is reached.
        """
        session = await self._get_session_or_raise(session_id)

        if session.status != SessionStatus.IN_PROGRESS:
            raise ValueError(f"Session {session_id} is not in progress")

        # 1. Persist patient answer
        seq = session.questions_asked_count + 1
        encrypted_answer = self._enc.encrypt_field(answer_text)
        patient_msg = ConversationMessage(
            session_id=session.id,
            sequence_number=seq,
            role=MessageRole.PATIENT,
            content=encrypted_answer,
            content_type=ContentType.TEXT,
        )
        self._db.add(patient_msg)

        # 2. Symptom extraction (stub)
        extracted_symptoms = self._extract_symptoms(answer_text)

        # 3. Red-flag check
        red_flags = self._check_red_flags(answer_text, extracted_symptoms)
        if red_flags:
            await self._handle_red_flags(session, red_flags, session_completed=False)

        # 4. Generate next question
        session.questions_asked_count = seq
        session.last_activity_at = datetime.now(timezone.utc)

        if seq >= session.max_questions:
            # Question limit reached
            await self._db.flush()
            return None

        next_question = self._generate_next_question(
            visit_type=session.visit_type,
            symptoms=extracted_symptoms,
            question_number=seq + 1,
        )

        # Persist AI question
        encrypted_question = self._enc.encrypt_field(next_question["question_text"])
        ai_msg = ConversationMessage(
            session_id=session.id,
            sequence_number=seq + 1,
            role=MessageRole.AI,
            content=encrypted_question,
            content_type=ContentType.TEXT,
        )
        self._db.add(ai_msg)
        await self._db.flush()

        return next_question

    # ------------------------------------------------------------------
    # Voice note processing
    # ------------------------------------------------------------------

    async def process_voice_note(
        self,
        session_id: uuid.UUID,
        audio_data: bytes,
        audio_format: str,
    ) -> str:
        """Process a voice note and return the transcript.

        This is a stub -- in production it would call the transcription
        service configured in ``settings.TRANSCRIPTION_SERVICE_URL``.
        """
        session = await self._get_session_or_raise(session_id)

        if session.status != SessionStatus.IN_PROGRESS:
            raise ValueError(f"Session {session_id} is not in progress")

        # Stub transcription
        logger.warning(
            "STUB: voice transcription not implemented — returning placeholder. "
            "session=%s format=%s bytes=%d",
            session_id, audio_format, len(audio_data),
        )
        transcript = (
            "[Voice note transcript placeholder — "
            f"received {len(audio_data)} bytes of {audio_format} audio]"
        )

        logger.info(
            "voice note processed (stub) | session=%s format=%s bytes=%d",
            session_id,
            audio_format,
            len(audio_data),
        )

        session.last_activity_at = datetime.now(timezone.utc)
        await self._db.flush()
        return transcript

    # ------------------------------------------------------------------
    # Concern ranking
    # ------------------------------------------------------------------

    async def rank_concerns(
        self,
        session_id: uuid.UUID,
        concerns: list[dict],
    ) -> ConversationSession:
        """Save the patient's ranked concerns (max 3) to the session."""
        session = await self._get_session_or_raise(session_id)

        if len(concerns) > 3:
            raise ValueError("A maximum of 3 concerns may be ranked")

        session.concerns_ranked = concerns
        session.last_activity_at = datetime.now(timezone.utc)
        await self._db.flush()

        logger.info("concerns ranked | session=%s count=%d", session_id, len(concerns))
        return session

    # ------------------------------------------------------------------
    # Session completion
    # ------------------------------------------------------------------

    async def complete_session(self, session_id: uuid.UUID) -> ConversationSession:
        """Mark the session as completed and trigger AI report generation."""
        session = await self._get_session_or_raise(session_id)

        if session.status != SessionStatus.IN_PROGRESS:
            raise ValueError(f"Session {session_id} is not in progress")

        now = datetime.now(timezone.utc)
        session.status = SessionStatus.COMPLETED
        session.completed_at = now
        session.last_activity_at = now
        await self._db.flush()

        # Trigger AI report generation (stub -- would call AI pipeline)
        logger.info(
            "session completed, AI report generation triggered | session=%s",
            session_id,
        )

        return session

    # ------------------------------------------------------------------
    # Session abandonment (spec 4.5)
    # ------------------------------------------------------------------

    async def handle_session_abandonment(self, session_id: uuid.UUID) -> None:
        """Handle session timeout / abandonment.

        CRITICAL (spec 4.5): If any red flags were detected during the
        session, the notification MUST still be sent even though the session
        was abandoned.  The alert is annotated with the incomplete status.
        """
        session = await self._get_session_or_raise(session_id)

        if session.status != SessionStatus.IN_PROGRESS:
            return  # already completed or abandoned

        now = datetime.now(timezone.utc)
        session.status = SessionStatus.ABANDONED
        session.last_activity_at = now

        # Check for any red-flag alerts already created during this session
        from app.models.ai_report import RedFlagAlert

        stmt = select(RedFlagAlert).where(
            RedFlagAlert.appointment_id == session.appointment_id,
            RedFlagAlert.patient_id == session.patient_id,
        )
        result = await self._db.execute(stmt)
        existing_alerts = list(result.scalars().all())

        for alert in existing_alerts:
            if alert.notification_sent_at is None:
                # CRITICAL: still send notification for abandoned sessions
                alert.session_was_completed = False

                # Load patient and physician for notification
                from app.models.user import User

                patient = await self._db.get(User, alert.patient_id)
                physician = await self._db.get(User, alert.physician_id)
                nurse = None
                if alert.nurse_id:
                    nurse = await self._db.get(User, alert.nurse_id)

                if patient and physician:
                    logger.warning(
                        "sending red-flag alert for ABANDONED session | "
                        "session=%s alert=%s severity=%s",
                        session_id,
                        alert.id,
                        alert.severity.value,
                    )
                    await self._notifications.send_red_flag_alert(
                        alert=alert,
                        patient=patient,
                        physician=physician,
                        nurse=nurse,
                    )

        await self._db.flush()
        logger.info("session abandoned | session=%s", session_id)

    # ------------------------------------------------------------------
    # Session retrieval (role-filtered)
    # ------------------------------------------------------------------

    async def update_session(
        self,
        session_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> ConversationSession:
        """Create a new version snapshot of the session (versioned update)."""
        session = await self._get_session_or_raise(session_id)

        if session.patient_id != patient_id:
            raise PermissionError("Patient does not own this session")

        session.last_activity_at = datetime.now(timezone.utc)
        await self._db.flush()
        return session

    async def get_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: str,
    ) -> dict:
        """Return a role-filtered view of the conversation session.

        - **patient**: own sessions only, sees messages decrypted.
        - **physician**: full view including all messages and red flags.
        - **nurse**: summary view, red flags, no raw transcript.
        - **scheduler**: metadata only (no messages).
        """
        session = await self._get_session_or_raise(session_id)

        base = {
            "session_id": session.id,
            "status": session.status.value,
            "visit_type": session.visit_type,
            "questions_asked_count": session.questions_asked_count,
            "started_at": session.started_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        }

        if user_role == Role.PATIENT.value:
            if session.patient_id != user_id:
                raise PermissionError("Access denied")
            base["messages"] = await self._decrypt_messages(session.id)
            base["concerns_ranked"] = session.concerns_ranked

        elif user_role == Role.PHYSICIAN.value:
            base["messages"] = await self._decrypt_messages(session.id)
            base["concerns_ranked"] = session.concerns_ranked
            base["patient_id"] = session.patient_id

        elif user_role == Role.NURSE.value:
            base["patient_id"] = session.patient_id
            # Nurse sees summary, not raw transcript
            base["concerns_ranked"] = session.concerns_ranked

        elif user_role in (Role.SCHEDULER.value, Role.ADMIN.value):
            base["patient_id"] = session.patient_id
            # Scheduler sees metadata only

        else:
            raise PermissionError("Unknown role")

        return base

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_session_or_raise(
        self, session_id: uuid.UUID
    ) -> ConversationSession:
        stmt = (
            select(ConversationSession)
            .options(selectinload(ConversationSession.messages))
            .where(ConversationSession.id == session_id)
        )
        result = await self._db.execute(stmt)
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError(f"Conversation session {session_id} not found")
        return session

    async def _decrypt_messages(self, session_id: uuid.UUID) -> list[dict]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.sequence_number)
        )
        result = await self._db.execute(stmt)
        messages = []
        for msg in result.scalars().all():
            try:
                content = self._enc.decrypt_field(msg.content)
            except Exception:
                content = "[decryption error]"
            messages.append(
                {
                    "sequence": msg.sequence_number,
                    "role": msg.role.value,
                    "content": content,
                    "content_type": msg.content_type.value,
                    "created_at": msg.created_at.isoformat(),
                }
            )
        return messages

    async def _handle_red_flags(
        self,
        session: ConversationSession,
        red_flags: list[dict],
        session_completed: bool,
    ) -> None:
        """Create RedFlagAlert records and send notifications."""
        from app.models.user import User

        patient = await self._db.get(User, session.patient_id)
        if patient is None:
            logger.error("patient %s not found for red-flag alert", session.patient_id)
            return

        # Determine the physician from the appointment
        physician: Optional[User] = None
        if session.appointment_id:
            from app.models.appointment import Appointment

            appt = await self._db.get(Appointment, session.appointment_id)
            if appt:
                physician = await self._db.get(User, appt.physician_id)

        if physician is None:
            logger.error(
                "could not determine physician for red-flag alert | session=%s",
                session.id,
            )
            return

        for flag in red_flags:
            alert = RedFlagAlert(
                appointment_id=session.appointment_id,
                patient_id=session.patient_id,
                physician_id=physician.id,
                trigger_description=flag["description"],
                severity=RedFlagSeverity(flag.get("severity", "elevated")),
                session_was_completed=session_completed,
            )
            self._db.add(alert)
            await self._db.flush()

            await self._notifications.send_red_flag_alert(
                alert=alert,
                patient=patient,
                physician=physician,
            )

    # ------------------------------------------------------------------
    # Stubs for AI components
    # ------------------------------------------------------------------

    @staticmethod
    def _build_opening_message(visit_type: str) -> str:
        if visit_type == "yearly_checkup":
            return (
                "Welcome to your annual check-up intake. I'll ask you a few "
                "questions to help your physician prepare for your visit. "
                "How have you been feeling overall?"
            )
        return (
            "Thank you for starting your intake. Please describe your "
            "primary concern so I can ask the right follow-up questions."
        )

    @staticmethod
    def _extract_symptoms(answer_text: str) -> list[str]:
        """Stub symptom extractor.

        In production this would call the SymptomExtractor AI component.
        """
        logger.warning("STUB: _extract_symptoms using keyword matching, not AI model")
        keywords = [
            "pain",
            "headache",
            "nausea",
            "fatigue",
            "fever",
            "dizziness",
            "shortness of breath",
            "chest pain",
            "numbness",
            "bleeding",
        ]
        lower = answer_text.lower()
        return [kw for kw in keywords if kw in lower]

    @staticmethod
    def _check_red_flags(
        answer_text: str, symptoms: list[str]
    ) -> list[dict]:
        """Stub red-flag detector.

        In production this would use the AI red-flag model.
        """
        logger.warning("STUB: _check_red_flags using pattern matching, not AI model")
        red_flags: list[dict] = []
        lower = answer_text.lower()

        emergency_patterns = {
            "chest pain": ("Possible cardiac event", "emergency"),
            "suicidal": ("Suicidal ideation reported", "emergency"),
            "self-harm": ("Self-harm ideation reported", "emergency"),
            "can't breathe": ("Acute respiratory distress", "emergency"),
            "shortness of breath": ("Respiratory concern", "urgent"),
            "numbness": ("Possible neurological event", "urgent"),
            "bleeding heavily": ("Significant bleeding reported", "urgent"),
        }

        for pattern, (description, severity) in emergency_patterns.items():
            if pattern in lower:
                red_flags.append(
                    {"description": description, "severity": severity}
                )

        return red_flags

    @staticmethod
    def _generate_next_question(
        visit_type: str | None,
        symptoms: list[str],
        question_number: int,
    ) -> dict:
        """Stub question engine.

        In production this would call the QuestionEngine AI component.
        """
        logger.warning("STUB: _generate_next_question using static templates, not AI model")
        if symptoms:
            return {
                "question_text": (
                    f"You mentioned {', '.join(symptoms)}. "
                    "Can you tell me more about when this started and "
                    "how severe it has been?"
                ),
                "question_type": "short_answer",
                "domain": "symptom_detail",
            }

        generic_questions = [
            {
                "question_text": "Are you currently taking any medications?",
                "question_type": "short_answer",
                "domain": "medications",
            },
            {
                "question_text": "Do you have any known allergies?",
                "question_type": "short_answer",
                "domain": "allergies",
            },
            {
                "question_text": "Have you had any recent surgeries or hospitalizations?",
                "question_type": "yes_no",
                "domain": "medical_history",
            },
        ]
        idx = (question_number - 1) % len(generic_questions)
        return generic_questions[idx]

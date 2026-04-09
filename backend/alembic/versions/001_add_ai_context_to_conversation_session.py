"""Add ai_context column to conversation_sessions

Revision ID: 001
Revises:
Create Date: 2026-04-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_sessions",
        sa.Column("ai_context", JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversation_sessions", "ai_context")

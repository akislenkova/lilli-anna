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
    # Use IF NOT EXISTS so re-running the migration on a DB that already has
    # the column (e.g. from a prior manual apply) doesn't fail.
    op.execute(
        "ALTER TABLE conversation_sessions "
        "ADD COLUMN IF NOT EXISTS ai_context JSON"
    )


def downgrade() -> None:
    op.drop_column("conversation_sessions", "ai_context")

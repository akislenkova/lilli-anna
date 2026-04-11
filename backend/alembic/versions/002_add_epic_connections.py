"""Add epic_connections table for patient SMART on FHIR tokens

Revision ID: 002
Revises: 90311ef16fe8
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "90311ef16fe8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS epic_connections (
            id          UUID        NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status      VARCHAR(20) NOT NULL DEFAULT 'pending',
            state       VARCHAR(256),
            code_verifier TEXT,
            access_token_enc  TEXT,
            refresh_token_enc TEXT,
            token_type  VARCHAR(50),
            scope       TEXT,
            expires_at  TIMESTAMPTZ,
            epic_patient_id VARCHAR(256),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_epic_connections_user_id "
        "ON epic_connections (user_id)"
    ))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_epic_connections_state "
        "ON epic_connections (state) WHERE state IS NOT NULL"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_epic_connections_state"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_epic_connections_user_id"))
    op.execute(sa.text("DROP TABLE IF EXISTS epic_connections"))

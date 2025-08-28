"""add tg_user_id, backfill, unique index

Revision ID: app_user_plan_tg_001
Revises: user_plan_001
Create Date: 2025-08-29 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "app_user_plan_tg_001"
down_revision = "user_plan_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("tg_user_id", sa.BigInteger(), nullable=True))

    # Ensure plan/pro_until/entitlements exist in case of drift (idempotent guards where possible)
    # Note: Alembic doesn't natively support IF NOT EXISTS for add_column across all DBs,
    # but our chain already added these in revision user_plan_001.

    # Backfill tg_user_id from pseudo email tg-<id>@tg.local
    op.execute(
        """
        UPDATE app_user
        SET tg_user_id = NULLIF(regexp_replace(email, '^tg-([0-9]+)@tg\\.local$', '\\1'), '')::bigint
        WHERE email LIKE 'tg-%@tg.local'
        """
    )

    # Create partial unique index on tg_user_id where not null
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_app_user_tg_user_id
        ON app_user (tg_user_id) WHERE tg_user_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_app_user_tg_user_id")
    op.drop_column("app_user", "tg_user_id")


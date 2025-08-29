"""add tg_user_id, plan, pro_until, entitlements, real_email, updated_at

revision = "0004_app_user_billing"
down_revision = "0003"
Create Date: 2025-08-30 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0004_app_user_billing"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Columns
    op.add_column("app_user", sa.Column("tg_user_id", sa.BigInteger(), nullable=True))
    op.add_column("app_user", sa.Column("plan", sa.String(length=16), nullable=False, server_default="free"))
    op.add_column("app_user", sa.Column("pro_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "app_user",
        sa.Column(
            "entitlements",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("app_user", sa.Column("real_email", sa.Text(), nullable=True))
    op.add_column(
        "app_user",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Backfill tg_user_id from pseudo email tg-<id>@tg.local
    op.execute(
        r"""
        UPDATE app_user
        SET tg_user_id = NULLIF(regexp_replace(email, '^tg-([0-9]+)@tg\\.local$', '\\1'), '')::bigint
        WHERE email LIKE 'tg-%@tg.local'
        AND tg_user_id IS NULL;
        """
    )

    # Partial unique index on tg_user_id when not null
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_app_user_tg_user_id
        ON app_user (tg_user_id) WHERE tg_user_id IS NOT NULL
        """
    )

    # updated_at trigger function (idempotent create/replace)
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$;

        DROP TRIGGER IF EXISTS trg_app_user_updated_at ON app_user;
        CREATE TRIGGER trg_app_user_updated_at
        BEFORE UPDATE ON app_user
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_app_user_updated_at ON app_user;")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
    op.execute("DROP INDEX IF EXISTS ux_app_user_tg_user_id;")
    op.drop_column("app_user", "updated_at")
    op.drop_column("app_user", "real_email")
    op.drop_column("app_user", "entitlements")
    op.drop_column("app_user", "pro_until")
    op.drop_column("app_user", "plan")
    op.drop_column("app_user", "tg_user_id")


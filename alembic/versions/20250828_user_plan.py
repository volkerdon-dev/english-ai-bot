"""add user plan and entitlements

Revision ID: user_plan_001
Revises: 0002
Create Date: 2025-08-28 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "user_plan_001"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_column("app_user", "entitlements")
    op.drop_column("app_user", "pro_until")
    op.drop_column("app_user", "plan")


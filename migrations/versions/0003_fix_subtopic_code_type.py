from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_fix_subtopic_code_type"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safely cast existing integers to text, only if column exists
    op.execute(
        r"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'lesson' AND column_name = 'subtopic_code'
            ) THEN
                ALTER TABLE lesson
                ALTER COLUMN subtopic_code TYPE text USING subtopic_code::text;
            END IF;
        END
        $$;
        """
    )



def downgrade() -> None:
    # Revert to integer if the column exists and is text-compatible
    op.execute(
        r"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'lesson' AND column_name = 'subtopic_code'
            ) THEN
                ALTER TABLE lesson
                ALTER COLUMN subtopic_code TYPE integer USING NULLIF(subtopic_code, '')::integer;
            END IF;
        END
        $$;
        """
    )
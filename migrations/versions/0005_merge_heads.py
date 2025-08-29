# migrations/versions/0005_merge_heads.py
from alembic import op
import sqlalchemy as sa

# Эта миграция просто склеивает две «головы» в одну,
# никаких изменений схемы не делает.

# Укажи любой уникальный идентификатор ревизии:
revision = "0005_merge_heads"
# ВАЖНО: перечисляем ВСЕ текущие heads
down_revision = ("0003_fix_subtopic_code_type", "20250830_app_user_add_tg_and_billing")
branch_labels = None
depends_on = None

def upgrade():
    # no-op: merge only
    pass

def downgrade():
    # no-op
    pass

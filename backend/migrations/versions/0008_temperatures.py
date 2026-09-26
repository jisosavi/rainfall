"""allow negative values for temperatures (temp_mean, temp_min, temp_max)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-26
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

OLD = "value IS NULL OR value >= 0"
NEW = "value IS NULL OR value >= 0 OR parameter LIKE 'temp_%'"


def _replace(condition: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("ck_daily_values_non_negative", "daily_values", type_="check")
        op.create_check_constraint("ck_daily_values_non_negative", "daily_values", condition)
    else:
        with op.batch_alter_table("daily_values", recreate="always") as batch:
            batch.drop_constraint("ck_daily_values_non_negative", type_="check")
            batch.create_check_constraint("ck_daily_values_non_negative", condition)


def upgrade() -> None:
    _replace(NEW)


def downgrade() -> None:
    op.execute("DELETE FROM daily_values WHERE parameter LIKE 'temp_%'")
    _replace(OLD)

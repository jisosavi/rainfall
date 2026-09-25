"""daily_values.flag (our own quality flag, e.g. suspect_spatial) and stations.elevation_m

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("daily_values", sa.Column("flag", sa.String(32), nullable=True))
    op.add_column("stations", sa.Column("elevation_m", sa.Double(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("daily_values") as batch:
        batch.drop_column("flag")
    with op.batch_alter_table("stations") as batch:
        batch.drop_column("elevation_m")

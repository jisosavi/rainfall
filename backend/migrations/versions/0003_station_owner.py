"""stations.owner: organisation running the station

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stations", sa.Column("owner", sa.String(255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("stations") as batch:
        batch.drop_column("owner")

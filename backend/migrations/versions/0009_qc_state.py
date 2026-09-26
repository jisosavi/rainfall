"""qc_state: the neighbour-check rules version each measurement was last fully checked with

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-26
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Empty at first: every measurement counts as checked with version 1, the rules before
    # this migration (see app.qc.RULES_VERSION), so only changed rules trigger a recheck.
    op.create_table(
        "qc_state",
        sa.Column("parameter", sa.String(32), primary_key=True),
        sa.Column("rules_version", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("qc_state")

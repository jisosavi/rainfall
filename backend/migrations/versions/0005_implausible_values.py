"""mark already stored implausible values as missing (see app.ingest.common.PLAUSIBLE_MAX)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-25
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# Kept here, not imported, so the migration stays fixed even if the limits change later.
LIMITS = {"precipitation": 300.0, "snow_depth": 600.0}


def upgrade() -> None:
    for parameter, limit in LIMITS.items():
        op.execute(
            f"""
            UPDATE daily_values
            SET value = NULL, has_data = false, raw_status = substr(coalesce(raw_status, '') || '|implausible', 1, 64)
            WHERE parameter = '{parameter}' AND value > {limit}
            """
        )


def downgrade() -> None:
    # The original values are still in raw_status; the next ingestion run restores them if
    # the plausibility check is removed. Nothing to undo in the schema.
    pass

"""indexes for the latest fetch per station and the dates with data per measurement

/api/status, get_data_status (latest fetch per source) and /api/dates, /api/years (distinct dates with data) read
every row of daily_values, about 10 s on the 0.5 GB Postgres, and hit the statement timeout (2026-11-06). With
these indexes each becomes a few thousand (status) or a few hundred (dates) index probes.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_daily_values_station_fetched", "daily_values", ["station_id", "fetched_at"])
    op.create_index(
        "ix_daily_values_parameter_date_with_data", "daily_values", ["parameter", "date"],
        postgresql_where=sa.text("has_data"), sqlite_where=sa.text("has_data"),
    )


def downgrade() -> None:
    op.drop_index("ix_daily_values_parameter_date_with_data", table_name="daily_values")
    op.drop_index("ix_daily_values_station_fetched", table_name="daily_values")

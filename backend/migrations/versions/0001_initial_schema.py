"""initial schema: stations and daily_precipitation

Revision ID: 0001
Revises:
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_station_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lon", sa.Double(), nullable=False),
        sa.Column("country", sa.String(2), nullable=False, server_default="FI"),
        sa.Column("region", sa.String(255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "daily_precipitation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "station_id",
            sa.Uuid(),
            sa.ForeignKey("stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("precipitation_mm", sa.Double(), nullable=True),
        sa.Column("has_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("raw_status", sa.String(64), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("station_id", "date", name="uq_daily_precipitation_station_date"),
        sa.CheckConstraint(
            "precipitation_mm IS NULL OR precipitation_mm >= 0",
            name="ck_daily_precipitation_non_negative",
        ),
        sa.CheckConstraint(
            "(has_data AND precipitation_mm IS NOT NULL) OR (NOT has_data AND precipitation_mm IS NULL)",
            name="ck_daily_precipitation_has_data_matches_value",
        ),
    )
    op.create_index("ix_daily_precipitation_date", "daily_precipitation", ["date"])


def downgrade() -> None:
    op.drop_index("ix_daily_precipitation_date", table_name="daily_precipitation")
    op.drop_table("daily_precipitation")
    op.drop_table("stations")

"""daily_precipitation -> daily_values with a parameter column (precipitation, snow_depth)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("daily_precipitation", "daily_values")
    if op.get_bind().dialect.name == "postgresql":
        # Postgres rewrites check constraints on column rename; only names need updating.
        op.alter_column("daily_values", "precipitation_mm", new_column_name="value")
        op.add_column(
            "daily_values",
            sa.Column("parameter", sa.String(32), nullable=False, server_default="precipitation"),
        )
        op.execute("ALTER TABLE daily_values RENAME CONSTRAINT ck_daily_precipitation_non_negative TO ck_daily_values_non_negative")
        op.execute(
            "ALTER TABLE daily_values RENAME CONSTRAINT ck_daily_precipitation_has_data_matches_value "
            "TO ck_daily_values_has_data_matches_value"
        )
        op.execute("ALTER TABLE daily_values RENAME CONSTRAINT daily_precipitation_pkey TO daily_values_pkey")
        op.execute(
            "ALTER TABLE daily_values RENAME CONSTRAINT daily_precipitation_station_id_fkey TO daily_values_station_id_fkey"
        )
        op.drop_constraint("uq_daily_precipitation_station_date", "daily_values", type_="unique")
        op.create_unique_constraint(
            "uq_daily_values_station_parameter_date", "daily_values", ["station_id", "parameter", "date"]
        )
        op.drop_index("ix_daily_precipitation_date", table_name="daily_values")
    else:
        # SQLite (local dev only): rebuild the table with the new column names and constraints.
        op.drop_index("ix_daily_precipitation_date", table_name="daily_values")
        with op.batch_alter_table("daily_values", recreate="always") as batch:
            batch.alter_column("precipitation_mm", new_column_name="value")
            batch.add_column(sa.Column("parameter", sa.String(32), nullable=False, server_default="precipitation"))
            batch.drop_constraint("uq_daily_precipitation_station_date", type_="unique")
            batch.drop_constraint("ck_daily_precipitation_non_negative", type_="check")
            batch.drop_constraint("ck_daily_precipitation_has_data_matches_value", type_="check")
            batch.create_unique_constraint("uq_daily_values_station_parameter_date", ["station_id", "parameter", "date"])
            batch.create_check_constraint("ck_daily_values_non_negative", "value IS NULL OR value >= 0")
            batch.create_check_constraint(
                "ck_daily_values_has_data_matches_value",
                "(has_data AND value IS NOT NULL) OR (NOT has_data AND value IS NULL)",
            )
    op.create_index("ix_daily_values_parameter_date", "daily_values", ["parameter", "date"])


def downgrade() -> None:
    op.execute("DELETE FROM daily_values WHERE parameter <> 'precipitation'")
    op.drop_index("ix_daily_values_parameter_date", table_name="daily_values")
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("uq_daily_values_station_parameter_date", "daily_values", type_="unique")
        op.create_unique_constraint("uq_daily_precipitation_station_date", "daily_values", ["station_id", "date"])
        op.drop_column("daily_values", "parameter")
        op.alter_column("daily_values", "value", new_column_name="precipitation_mm")
        op.execute("ALTER TABLE daily_values RENAME CONSTRAINT ck_daily_values_non_negative TO ck_daily_precipitation_non_negative")
        op.execute(
            "ALTER TABLE daily_values RENAME CONSTRAINT ck_daily_values_has_data_matches_value "
            "TO ck_daily_precipitation_has_data_matches_value"
        )
        op.execute("ALTER TABLE daily_values RENAME CONSTRAINT daily_values_pkey TO daily_precipitation_pkey")
        op.execute(
            "ALTER TABLE daily_values RENAME CONSTRAINT daily_values_station_id_fkey TO daily_precipitation_station_id_fkey"
        )
    else:
        with op.batch_alter_table("daily_values", recreate="always") as batch:
            batch.drop_constraint("uq_daily_values_station_parameter_date", type_="unique")
            batch.drop_constraint("ck_daily_values_non_negative", type_="check")
            batch.drop_constraint("ck_daily_values_has_data_matches_value", type_="check")
            batch.drop_column("parameter")
            batch.alter_column("value", new_column_name="precipitation_mm")
            batch.create_unique_constraint("uq_daily_precipitation_station_date", ["station_id", "date"])
            batch.create_check_constraint("ck_daily_precipitation_non_negative", "precipitation_mm IS NULL OR precipitation_mm >= 0")
            batch.create_check_constraint(
                "ck_daily_precipitation_has_data_matches_value",
                "(has_data AND precipitation_mm IS NOT NULL) OR (NOT has_data AND precipitation_mm IS NULL)",
            )
    op.rename_table("daily_values", "daily_precipitation")
    op.create_index("ix_daily_precipitation_date", "daily_precipitation", ["date"])

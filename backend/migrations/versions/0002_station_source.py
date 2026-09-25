"""stations.source: allow several data sources (FMI, MET Norway)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows are all FMI stations.
    with op.batch_alter_table("stations", recreate="auto") as batch:
        batch.add_column(sa.Column("source", sa.String(16), nullable=False, server_default="fmi"))
    if op.get_bind().dialect.name == "postgresql":
        # Name Postgres gave the unnamed UNIQUE (source_station_id) from 0001.
        op.drop_constraint("stations_source_station_id_key", "stations", type_="unique")
        op.create_unique_constraint("uq_stations_source_station", "stations", ["source", "source_station_id"])
    else:
        # SQLite (local dev only): the 0001 constraint is unnamed, so give reflected unique
        # constraints a name in order to drop it while the table is rebuilt.
        with op.batch_alter_table(
            "stations",
            recreate="always",
            naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
        ) as batch:
            batch.drop_constraint("uq_stations_source_station_id", type_="unique")
            batch.create_unique_constraint("uq_stations_source_station", ["source", "source_station_id"])


def downgrade() -> None:
    op.execute("DELETE FROM stations WHERE source <> 'fmi'")
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("uq_stations_source_station", "stations", type_="unique")
        op.create_unique_constraint("stations_source_station_id_key", "stations", ["source_station_id"])
        op.drop_column("stations", "source")
    else:
        with op.batch_alter_table("stations", recreate="always") as batch:
            batch.drop_constraint("uq_stations_source_station", type_="unique")
            batch.drop_column("source")
            batch.create_unique_constraint("uq_stations_source_station_id", ["source_station_id"])

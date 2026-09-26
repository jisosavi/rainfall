"""IMO rainfall: add missing rows for days without a value (show as hollow circles)

Until now only reported Icelandic rainfall days were stored, so a station vanished from the
map on days without data. Ingestion now stores missing rows; this fills them in for rows
already stored: every day from a station's first to its last stored rainfall date.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-26
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return  # local SQLite databases get the rows on their next ingestion run
    op.execute(
        """
        INSERT INTO daily_values (id, station_id, parameter, date, value, has_data, raw_status)
        SELECT gen_random_uuid(), r.station_id, 'precipitation', d::date, NULL, false, 'missing'
        FROM (
            SELECT v.station_id, min(v.date) AS first_day, max(v.date) AS last_day
            FROM daily_values v JOIN stations s ON s.id = v.station_id
            WHERE s.source = 'imo' AND v.parameter = 'precipitation'
            GROUP BY v.station_id
        ) r
        CROSS JOIN LATERAL generate_series(r.first_day, r.last_day, interval '1 day') AS d
        ON CONFLICT (station_id, parameter, date) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM daily_values
        WHERE parameter = 'precipitation' AND raw_status = 'missing'
          AND station_id IN (SELECT id FROM stations WHERE source = 'imo')
        """
    )

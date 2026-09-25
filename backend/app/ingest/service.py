import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import DailyPrecipitation, Station
from app.ingest.common import StationSeries, date_chunks

logger = logging.getLogger(__name__)

BATCH_SIZE = 2000

FetchChunk = Callable[[date, date], list[StationSeries]]


def _insert(session: Session, model):
    dialect = session.get_bind().dialect.name
    return (pg_insert if dialect == "postgresql" else sqlite_insert)(model)


def upsert_stations(session: Session, series: list[StationSeries]) -> dict[tuple[str, str], UUID]:
    if not series:
        return {}
    rows = {
        (s.source, s.source_station_id): {
            "id": uuid4(),
            "source": s.source,
            "source_station_id": s.source_station_id,
            "name": s.name,
            "lat": s.lat,
            "lon": s.lon,
            "country": s.country,
            "region": s.region,
        }
        for s in series
    }
    stmt = _insert(session, Station).values(list(rows.values()))
    stmt = stmt.on_conflict_do_update(
        index_elements=[Station.source, Station.source_station_id],
        set_={
            "name": stmt.excluded.name,
            "lat": stmt.excluded.lat,
            "lon": stmt.excluded.lon,
            "country": stmt.excluded.country,
            "region": stmt.excluded.region,
        },
    )
    session.execute(stmt)
    sources = {s.source for s in series}
    result = session.execute(
        select(Station.source, Station.source_station_id, Station.id)
        .where(Station.source.in_(sources))
        .where(Station.source_station_id.in_([key[1] for key in rows]))
    )
    return {(source, source_id): station_id for source, source_id, station_id in result}


def upsert_precipitation(session: Session, series: list[StationSeries], station_ids: dict[tuple[str, str], UUID]) -> int:
    rows = [
        {
            "id": uuid4(),
            "station_id": station_ids[(s.source, s.source_station_id)],
            "date": day,
            "precipitation_mm": value.precipitation_mm,
            "has_data": value.has_data,
            "raw_status": value.raw_status,
        }
        for s in series
        for day, value in s.values
    ]
    for i in range(0, len(rows), BATCH_SIZE):
        stmt = _insert(session, DailyPrecipitation).values(rows[i : i + BATCH_SIZE])
        stmt = stmt.on_conflict_do_update(
            index_elements=[DailyPrecipitation.station_id, DailyPrecipitation.date],
            set_={
                "precipitation_mm": stmt.excluded.precipitation_mm,
                "has_data": stmt.excluded.has_data,
                "raw_status": stmt.excluded.raw_status,
                "fetched_at": func.now(),
            },
        )
        session.execute(stmt)
    return len(rows)


def store_series(session: Session, series: list[StationSeries]) -> int:
    station_ids = upsert_stations(session, series)
    count = upsert_precipitation(session, series, station_ids)
    session.commit()
    return count


def default_range(
    session: Session, source: str, start_date: date, refetch_days: int, today: date | None = None
) -> tuple[date, date]:
    """From `refetch_days` before this source's newest stored row (or `start_date` if it has
    none) to yesterday (UTC)."""
    today = today or datetime.now(timezone.utc).date()
    end = today - timedelta(days=1)
    latest = session.execute(
        select(func.max(DailyPrecipitation.date)).join(Station).where(Station.source == source)
    ).scalar()
    start = start_date if latest is None else max(start_date, latest - timedelta(days=refetch_days))
    return start, end


def run_ingest(session: Session, fetch_chunk: FetchChunk, start: date, end: date, label: str = "") -> int:
    total = 0
    for chunk_start, chunk_end in date_chunks(start, end):
        series = fetch_chunk(chunk_start, chunk_end)
        count = store_series(session, series)
        total += count
        logger.info("%s %s..%s: %d stations, %d values", label, chunk_start, chunk_end, len(series), count)
    return total

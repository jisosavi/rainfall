import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import PRECIPITATION, DailyValue, Station
from app.ingest.common import StationSeries, check_plausible, date_chunks

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
            "owner": s.owner,
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
            "owner": stmt.excluded.owner,
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
    rows = []
    for s in series:
        for day, raw in s.values:
            value = check_plausible(s.parameter, raw)
            rows.append(
                {
                    "id": uuid4(),
                    "station_id": station_ids[(s.source, s.source_station_id)],
                    "parameter": s.parameter,
                    "date": day,
                    "value": value.value,
                    "has_data": value.has_data,
                    "raw_status": value.raw_status,
                }
            )
    for i in range(0, len(rows), BATCH_SIZE):
        stmt = _insert(session, DailyValue).values(rows[i : i + BATCH_SIZE])
        stmt = stmt.on_conflict_do_update(
            index_elements=[DailyValue.station_id, DailyValue.parameter, DailyValue.date],
            set_={
                "value": stmt.excluded.value,
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
    session: Session,
    source: str,
    start_date: date,
    refetch_days: int,
    today: date | None = None,
    parameters: tuple[str, ...] = (PRECIPITATION,),
) -> tuple[date, date]:
    """From `refetch_days` before this source's newest stored row to yesterday (UTC). If any of
    the source's parameters has no data yet (e.g. a newly added one), start from `start_date`."""
    today = today or datetime.now(timezone.utc).date()
    end = today - timedelta(days=1)
    latest_per_parameter = [
        session.execute(
            select(func.max(DailyValue.date))
            .join(Station)
            .where(Station.source == source, DailyValue.parameter == parameter)
        ).scalar()
        for parameter in parameters
    ]
    if any(latest is None for latest in latest_per_parameter):
        return start_date, end
    return max(start_date, min(latest_per_parameter) - timedelta(days=refetch_days)), end


def run_ingest(session: Session, fetch_chunk: FetchChunk, start: date, end: date, label: str = "") -> int:
    total = 0
    for chunk_start, chunk_end in date_chunks(start, end):
        series = fetch_chunk(chunk_start, chunk_end)
        count = store_series(session, series)
        total += count
        logger.info("%s %s..%s: %d stations, %d values", label, chunk_start, chunk_end, len(series), count)
    return total

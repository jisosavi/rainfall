import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import DailyPrecipitation, Station
from app.ingest.fmi import StationSeries, date_chunks, fetch_daily, normalize

logger = logging.getLogger(__name__)

BATCH_SIZE = 2000


def _insert(session: Session, model):
    dialect = session.get_bind().dialect.name
    return (pg_insert if dialect == "postgresql" else sqlite_insert)(model)


def upsert_stations(session: Session, series: list[StationSeries]) -> dict[str, UUID]:
    if not series:
        return {}
    rows = {
        s.fmisid: {
            "id": uuid4(),
            "source_station_id": s.fmisid,
            "name": s.name,
            "lat": s.lat,
            "lon": s.lon,
            "country": "FI",
            "region": s.region,
        }
        for s in series
    }
    stmt = _insert(session, Station).values(list(rows.values()))
    stmt = stmt.on_conflict_do_update(
        index_elements=[Station.source_station_id],
        set_={"name": stmt.excluded.name, "lat": stmt.excluded.lat, "lon": stmt.excluded.lon, "region": stmt.excluded.region},
    )
    session.execute(stmt)
    result = session.execute(
        select(Station.source_station_id, Station.id).where(Station.source_station_id.in_(list(rows)))
    )
    return {source_id: station_id for source_id, station_id in result}


def upsert_precipitation(session: Session, series: list[StationSeries], station_ids: dict[str, UUID]) -> int:
    rows = []
    for s in series:
        for day, raw in s.values:
            value = normalize(raw)
            rows.append(
                {
                    "id": uuid4(),
                    "station_id": station_ids[s.fmisid],
                    "date": day,
                    "precipitation_mm": value.precipitation_mm,
                    "has_data": value.has_data,
                    "raw_status": value.raw_status,
                }
            )
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


def default_range(session: Session, start_date: date, refetch_days: int, today: date | None = None) -> tuple[date, date]:
    """From `refetch_days` before the newest stored row (or `start_date` on an empty DB) to yesterday (UTC)."""
    today = today or datetime.now(timezone.utc).date()
    end = today - timedelta(days=1)
    latest = session.execute(select(func.max(DailyPrecipitation.date))).scalar()
    start = start_date if latest is None else max(start_date, latest - timedelta(days=refetch_days))
    return start, end


def run_ingest(session: Session, client: httpx.Client, start: date, end: date) -> int:
    total = 0
    for chunk_start, chunk_end in date_chunks(start, end):
        series = fetch_daily(client, chunk_start, chunk_end)
        count = store_series(session, series)
        total += count
        logger.info("%s..%s: %d stations, %d values", chunk_start, chunk_end, len(series), count)
    return total

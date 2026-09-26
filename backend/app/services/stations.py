"""Station and series queries: a date's stations, one station's values, search and coverage."""

import math
import statistics
import time
from datetime import date, timedelta
from threading import Lock
from uuid import UUID

from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import PARAMETERS, PRECIPITATION, SNOW_DEPTH, UNITS, DailyValue, Station
from app.qc import SUSPECT_SPATIAL
from app.schemas.queries import (
    Coverage,
    ObservationSeries,
    Observations,
    SeriesSummary,
    SeriesValue,
    StationInfo,
    StationSummary,
)
from app.schemas.station import (
    HistoryValue,
    LastDataResponse,
    StationDay,
    StationHistoryResponse,
    StationsForDateResponse,
)
from app.services.errors import InvalidRequestError, NotFoundError

MAX_HISTORY_DAYS = 366
MAX_SEARCH_RESULTS = 20
RECENT_DAYS = 400  # a station "reports" a measurement if it has data in this many days
MEASUREMENTS_CACHE_SECONDS = 30 * 60


def latest_date(db: Session, parameter: str) -> date | None:
    return db.execute(
        select(func.max(DailyValue.date)).where(DailyValue.parameter == parameter, DailyValue.has_data.is_(True))
    ).scalar()


def resolve_date(db: Session, date_value: date | None, parameter: str) -> date:
    if date_value is not None:
        return date_value
    latest = latest_date(db, parameter)
    if latest is None:
        raise NotFoundError(f"No {parameter} data available yet.")
    return latest


def get_station(db: Session, station_id: UUID) -> Station:
    station = db.get(Station, station_id)
    if station is None:
        raise NotFoundError("Station not found.")
    return station


def _compat_mm(parameter: str, value: float | None) -> float | None:
    return value if parameter == PRECIPITATION else None


def _station_day(station: Station, day: date, parameter: str, record: DailyValue | None) -> StationDay:
    value = record.value if record else None
    return StationDay(
        id=station.id,
        source=station.source,
        source_station_id=station.source_station_id,
        name=station.name,
        lat=station.lat,
        lon=station.lon,
        country=station.country,
        region=station.region,
        owner=station.owner,
        elevation_m=station.elevation_m,
        date=day,
        parameter=parameter,
        value=value,
        unit=UNITS[parameter],
        precipitation_mm=_compat_mm(parameter, value),
        has_data=record.has_data if record else False,
        flag=record.flag if record else None,
    )


def stations_for_date(db: Session, date_value: date | None, parameter: str) -> StationsForDateResponse:
    day = resolve_date(db, date_value, parameter)
    # Ingestion stores a row (has_data=false) for every station a source reports that day, even
    # when the value is missing, so joining on rows shows operating stations and hides closed ones.
    rows = db.execute(
        select(Station, DailyValue)
        .join(
            DailyValue,
            and_(DailyValue.station_id == Station.id, DailyValue.parameter == parameter, DailyValue.date == day),
        )
        .where(Station.active.is_(True))
        .order_by(Station.name.asc())
    ).all()
    return StationsForDateResponse(
        date=day,
        parameter=parameter,
        unit=UNITS[parameter],
        stations=[_station_day(station, day, parameter, record) for station, record in rows],
    )


def station_day(db: Session, station_id: UUID, date_value: date | None, parameter: str) -> StationDay:
    station = get_station(db, station_id)
    day = resolve_date(db, date_value, parameter)
    record = db.execute(
        select(DailyValue).where(
            DailyValue.station_id == station_id, DailyValue.parameter == parameter, DailyValue.date == day
        )
    ).scalar_one_or_none()
    return _station_day(station, day, parameter, record)


def _range(db: Session, start: date | None, end: date | None, parameter: str, default_days: int = 30) -> tuple[date, date]:
    end = resolve_date(db, end, parameter)
    start = start or end - timedelta(days=default_days - 1)
    if start > end:
        raise InvalidRequestError("start must not be after end.")
    if (end - start).days >= MAX_HISTORY_DAYS:
        raise InvalidRequestError(f"Range is limited to {MAX_HISTORY_DAYS} days.")
    return start, end


def _values(db: Session, station_id: UUID, parameter: str, start: date, end: date) -> list[DailyValue]:
    return list(
        db.execute(
            select(DailyValue)
            .where(DailyValue.station_id == station_id, DailyValue.parameter == parameter)
            .where(DailyValue.date.between(start, end))
            .order_by(DailyValue.date.asc())
        ).scalars()
    )


def station_history(
    db: Session, station_id: UUID, start: date | None, end: date | None, parameter: str
) -> StationHistoryResponse:
    get_station(db, station_id)
    start, end = _range(db, start, end, parameter)
    return StationHistoryResponse(
        station_id=station_id,
        parameter=parameter,
        unit=UNITS[parameter],
        start=start,
        end=end,
        values=[
            HistoryValue(
                date=r.date, value=r.value, precipitation_mm=_compat_mm(parameter, r.value), has_data=r.has_data, flag=r.flag
            )
            for r in _values(db, station_id, parameter, start, end)
        ],
    )


def last_data(db: Session, station_id: UUID, before: date | None, parameter: str) -> LastDataResponse:
    """For a station without data on a date: when it last had a value."""
    get_station(db, station_id)
    query = (
        select(DailyValue.date, DailyValue.value)
        .where(DailyValue.station_id == station_id, DailyValue.parameter == parameter, DailyValue.has_data.is_(True))
        .order_by(DailyValue.date.desc())
        .limit(1)
    )
    if before is not None:
        query = query.where(DailyValue.date <= before)
    row = db.execute(query).first()
    return LastDataResponse(
        station_id=station_id,
        parameter=parameter,
        unit=UNITS[parameter],
        date=row.date if row else None,
        value=row.value if row else None,
    )


def available_dates(db: Session, year: int | None, parameter: str) -> list[date]:
    query = (
        select(DailyValue.date)
        .where(DailyValue.parameter == parameter, DailyValue.has_data.is_(True))
        .distinct()
        .order_by(DailyValue.date.desc())
    )
    if year is not None:
        query = query.where(DailyValue.date.between(date(year, 1, 1), date(year, 12, 31)))
    return list(db.execute(query).scalars().all())


def available_years(db: Session, parameter: str) -> list[int]:
    year = extract("year", DailyValue.date)
    rows = db.execute(
        select(year).where(DailyValue.parameter == parameter, DailyValue.has_data.is_(True)).distinct().order_by(year)
    ).scalars().all()
    return [int(y) for y in rows]


# --- Search and coverage (for agents) ---------------------------------------------------

_measurements_cache: dict = {"at": 0.0, "value": {}}
_measurements_lock = Lock()


def recent_measurements(db: Session) -> dict[UUID, list[str]]:
    """Station id -> measurements with data in the last RECENT_DAYS days. A full-table scan,
    so the result is cached for MEASUREMENTS_CACHE_SECONDS."""
    with _measurements_lock:
        if time.monotonic() - _measurements_cache["at"] < MEASUREMENTS_CACHE_SECONDS and _measurements_cache["value"]:
            return _measurements_cache["value"]
        since = date.today() - timedelta(days=RECENT_DAYS)
        rows = db.execute(
            select(DailyValue.station_id, DailyValue.parameter)
            .where(DailyValue.date >= since, DailyValue.has_data.is_(True))
            .distinct()
        ).all()
        result: dict[UUID, list[str]] = {}
        for station_id, parameter in rows:
            result.setdefault(station_id, []).append(parameter)
        for station_id in result:
            result[station_id].sort(key=PARAMETERS.index)
        _measurements_cache.update(at=time.monotonic(), value=result)
        return result


def clear_measurements_cache() -> None:
    with _measurements_lock:
        _measurements_cache.update(at=0.0, value={})


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _summary(station: Station, measurements: list[str], distance_km: float | None = None) -> StationSummary:
    return StationSummary(
        id=station.id,
        source=station.source,
        source_station_id=station.source_station_id,
        name=station.name,
        country=station.country,
        region=station.region,
        owner=station.owner,
        lat=station.lat,
        lon=station.lon,
        elevation_m=station.elevation_m,
        distance_km=round(distance_km, 1) if distance_km is not None else None,
        measurements=measurements,
    )


def find_stations(
    db: Session,
    *,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 50,
    name: str | None = None,
    countries: list[str] | None = None,
    parameter: str | None = None,
    limit: int = MAX_SEARCH_RESULTS,
) -> list[StationSummary]:
    """Active stations near a point (nearest first) and/or matching a name, optionally only in
    some countries (station country codes) and only those reporting a measurement."""
    if (lat is None) != (lon is None):
        raise InvalidRequestError("Give both lat and lon, or neither.")
    if lat is None and not name:
        raise InvalidRequestError("Give a point (lat, lon) or a name to search for.")
    query = select(Station).where(Station.active.is_(True))
    if name:
        query = query.where(or_(Station.name.ilike(f"%{name.strip()}%"), Station.region.ilike(f"%{name.strip()}%")))
    if countries:
        query = query.where(Station.country.in_(countries))
    measurements = recent_measurements(db)
    found: list[tuple[float | None, Station]] = []
    for station in db.execute(query).scalars():
        reported = measurements.get(station.id, [])
        if parameter and parameter not in reported:
            continue
        distance = km_between(lat, lon, station.lat, station.lon) if lat is not None else None
        if distance is not None and distance > radius_km:
            continue
        found.append((distance, station))
    found.sort(key=lambda item: (item[0] if item[0] is not None else 0, item[1].name))
    limit = max(1, min(limit, MAX_SEARCH_RESULTS))
    return [_summary(s, measurements.get(s.id, []), d) for d, s in found[:limit]]


def station_info(db: Session, station_id: UUID) -> StationInfo:
    station = get_station(db, station_id)
    rows = db.execute(
        select(DailyValue.parameter, func.min(DailyValue.date), func.max(DailyValue.date), func.count())
        .where(DailyValue.station_id == station_id, DailyValue.has_data.is_(True))
        .group_by(DailyValue.parameter)
    ).all()
    coverage = sorted(
        (Coverage(parameter=p, unit=UNITS[p], first_date=first, last_date=last, days_with_data=n) for p, first, last, n in rows),
        key=lambda c: PARAMETERS.index(c.parameter),
    )
    recent = date.today() - timedelta(days=RECENT_DAYS)
    summary = _summary(station, [c.parameter for c in coverage if c.last_date >= recent])
    return StationInfo(**summary.model_dump(), coverage=coverage)


def summarize(parameter: str, values: list[SeriesValue], days: int) -> SeriesSummary:
    """Summary of a series; flagged (suspect) values are left out, as in rankings."""
    usable = [v for v in values if v.has_data and v.flag != SUSPECT_SPATIAL]
    flagged = sum(1 for v in values if v.flag == SUSPECT_SPATIAL)
    if not usable:
        return SeriesSummary(days=days, days_with_data=0, flagged=flagged)
    low = min(usable, key=lambda v: v.value)
    high = max(usable, key=lambda v: v.value)
    numbers = [v.value for v in usable]
    summary = SeriesSummary(
        days=days,
        days_with_data=len(usable),
        flagged=flagged,
        min=low.value,
        min_date=low.date,
        max=high.value,
        max_date=high.date,
        mean=round(statistics.mean(numbers), 1),
    )
    if parameter == PRECIPITATION:
        summary.total = round(sum(numbers), 1)
    if parameter in (PRECIPITATION, SNOW_DEPTH):
        summary.days_at_least_1 = sum(1 for n in numbers if n >= 1)
    return summary


def observations(
    db: Session, station_id: UUID, parameters: list[str], start: date | None, end: date | None
) -> Observations:
    """Daily values of one or more measurements at a station, each with a summary."""
    station = get_station(db, station_id)
    if not parameters:
        raise InvalidRequestError("Name at least one measurement.")
    # One range for all measurements: the latest date among them if no end is given.
    if end is None:
        latest = [d for d in (latest_date(db, p) for p in parameters) if d]
        if not latest:
            raise NotFoundError("No data available yet.")
        end = max(latest)
    start, end = _range(db, start, end, parameters[0])
    series = []
    for parameter in parameters:
        values = [SeriesValue(date=r.date, value=r.value, has_data=r.has_data, flag=r.flag) for r in _values(db, station_id, parameter, start, end)]
        series.append(
            ObservationSeries(
                parameter=parameter,
                unit=UNITS[parameter],
                summary=summarize(parameter, values, (end - start).days + 1),
                values=values,
            )
        )
    return Observations(
        station=_summary(station, recent_measurements(db).get(station.id, [])),
        start=start,
        end=end,
        series=series,
    )

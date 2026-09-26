"""Summaries across stations: one day in a country or area, and how fresh the data is."""

import statistics
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PARAMETERS, UNITS, DailyValue, Station
from app.qc import SUSPECT_SPATIAL
from app.schemas.queries import DataStatus, DayOverview, RankedValue, SourceStatus
from app.services.errors import InvalidRequestError
from app.services.rankings import COUNTRY_CODES
from app.services.stations import stations_for_date

MAX_TOP = 25
FRESHNESS_WINDOW_DAYS = 60  # latest dates are looked for this far back (keeps the query on the index)

BoundingBox = tuple[float, float, float, float]  # min lon, min lat, max lon, max lat


def day_overview(
    db: Session,
    date_value: date | None,
    parameter: str,
    country: str | None = None,
    bbox: BoundingBox | None = None,
    top: int = 10,
) -> DayOverview:
    """Stations reporting, extremes, mean and median, and the top (and, for temperature, bottom)
    stations for one date. Flagged values are counted but left out of the statistics."""
    if country is not None and country not in COUNTRY_CODES:
        raise InvalidRequestError(f"Unknown country '{country}'.")
    if bbox is not None:
        min_lon, min_lat, max_lon, max_lat = bbox
        if min_lon >= max_lon or min_lat >= max_lat:
            raise InvalidRequestError("bbox must be min_lon, min_lat, max_lon, max_lat.")
    day = stations_for_date(db, date_value, parameter)
    rows = day.stations
    if country is not None:
        rows = [s for s in rows if s.country in COUNTRY_CODES[country]]
    if bbox is not None:
        rows = [s for s in rows if min_lon <= s.lon <= max_lon and min_lat <= s.lat <= max_lat]
    reporting = [s for s in rows if s.has_data and s.value is not None]
    usable = [s for s in reporting if s.flag != SUSPECT_SPATIAL]
    top = max(1, min(top, MAX_TOP))

    def ranked(s) -> RankedValue:
        return RankedValue(station_id=s.id, name=s.name, country=s.country, value=s.value, flag=s.flag)

    by_value = sorted(usable, key=lambda s: (-s.value, s.name))
    values = [s.value for s in usable]
    return DayOverview(
        date=day.date,
        parameter=parameter,
        unit=UNITS[parameter],
        country=country,
        stations=len(rows),
        reporting=len(reporting),
        flagged=len(reporting) - len(usable),
        min=ranked(by_value[-1]) if by_value else None,
        max=ranked(by_value[0]) if by_value else None,
        mean=round(statistics.mean(values), 1) if values else None,
        median=round(statistics.median(values), 1) if values else None,
        highest=[ranked(s) for s in by_value[:top]],
        lowest=[ranked(s) for s in reversed(by_value[-top:])] if parameter.startswith("temp_") else [],
    )


def data_status(db: Session, today: date | None = None) -> DataStatus:
    """When each source was last fetched and its latest date with data per measurement."""
    today = today or date.today()
    fetched = dict(
        db.execute(select(Station.source, func.max(DailyValue.fetched_at)).join(DailyValue).group_by(Station.source)).all()
    )
    latest: dict[str, dict[str, date]] = {source: {} for source in fetched}
    since = today - timedelta(days=FRESHNESS_WINDOW_DAYS)
    for parameter in PARAMETERS:
        rows = db.execute(
            select(Station.source, func.max(DailyValue.date))
            .join(Station)
            .where(DailyValue.parameter == parameter, DailyValue.date >= since, DailyValue.has_data.is_(True))
            .group_by(Station.source)
        ).all()
        for source, last in rows:
            latest.setdefault(source, {})[parameter] = last
    sources = [
        SourceStatus(source=source, last_fetched=fetched.get(source), latest_date=latest.get(source, {}))
        for source in sorted(latest)
    ]
    return DataStatus(updated_at=max((f for f in fetched.values() if f), default=None), sources=sources)

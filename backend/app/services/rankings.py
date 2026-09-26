"""Top N rankings per station for a period ending on a date.

Rainfall: totals for the ISO week, calendar month or year up to the date, or the rolling
last 30 days. Snow depth: the depth on the date, the deepest since 1 October, or the days
with snow cover (>= 1 cm) since 1 October. Temperature (order=warmest or coldest): for
`now` the value on the date; for week, month, year and last30 the extreme of the period for
minimum and maximum (e.g. the coldest night of the month, with its date), and the period's
average for the mean.

Rainfall and snow stations whose score is 0 (no rain, no snow) aren't ranked, so a dry or snow-free period
gives an empty list rather than a list of zeros. Values flagged `suspect_spatial` (far above all neighbours, not confirmed by hourly
readings; for temperature far warmer or colder than the neighbours) count as missing, so they
never lift a station in a ranking. Totals, day counts and average temperatures need data on
at least 90% of the period's days by default; min_coverage=0 ranks all.
"""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import SNOW_DEPTH, TEMP_MEAN, UNITS, DailyValue, Station
from app.qc import SUSPECT_SPATIAL
from app.schemas.station import Parameter
from app.services.errors import InvalidRequestError

Period = Literal["week", "month", "year", "last30", "now", "winter_max", "winter_days"]
RAIN_PERIODS = {"week", "month", "year", "last30"}
SNOW_PERIODS = {"now", "winter_max", "winter_days"}
TEMP_PERIODS = {"now", "week", "month", "year", "last30"}
Order = Literal["warmest", "coldest"]
# Filter keys -> station country codes (Svalbard and Jan Mayen count as Norway).
COUNTRY_CODES = {"fi": ["FI"], "no": ["NO", "SJ"], "se": ["SE"], "dk": ["DK"], "gl": ["GL"], "fo": ["FO"], "is": ["IS"], "ee": ["EE"]}


class RankedStation(BaseModel):
    rank: int
    id: str
    source_station_id: str
    name: str
    country: str
    source: str
    lat: float
    lon: float
    region: str | None = None
    owner: str | None = None
    value: float
    days_with_data: int
    days: int  # days in the period
    coverage: float  # days_with_data / days
    on_date: date | None = None  # when the extreme happened (deepest snow, coldest night…)


class RankingsResponse(BaseModel):
    parameter: Parameter
    period: Period
    order: Order | None = None  # temperature only
    unit: str
    start: date
    end: date
    days: int
    min_coverage: float
    stations: list[RankedStation]


def period_range(period: str, end: date) -> tuple[date, date]:
    if period == "week":
        return end - timedelta(days=end.weekday()), end  # ISO week from Monday
    if period == "month":
        return end.replace(day=1), end
    if period == "year":
        return end.replace(month=1, day=1), end
    if period == "last30":
        return end - timedelta(days=29), end
    if period == "now":
        return end, end
    winter = end.year if end.month >= 10 else end.year - 1  # winter from 1 October
    return date(winter, 10, 1), end


def rankings(
    db: Session,
    *,
    period: str,
    date_value: date,
    parameter: str = "precipitation",
    country: str | None = None,
    limit: int = 15,
    min_coverage: float = 0.9,
    order: str = "warmest",
) -> RankingsResponse:
    """Top `limit` stations for `period` ending on `date_value` (see the module docstring)."""
    temperature = parameter.startswith("temp_")
    periods = TEMP_PERIODS if temperature else SNOW_PERIODS if parameter == SNOW_DEPTH else RAIN_PERIODS
    if period not in periods:
        raise InvalidRequestError(f"Period '{period}' doesn't apply to {parameter}.")
    if country is not None and country not in COUNTRY_CODES:
        raise InvalidRequestError(f"Unknown country '{country}'.")

    start, end = period_range(period, date_value)
    days = (end - start).days + 1
    counted = func.count(DailyValue.id)
    coldest = temperature and order == "coldest"
    # "Extreme" scores are one day's value, so they need no coverage and have a date.
    extreme = period in ("now", "winter_max") or (temperature and parameter != TEMP_MEAN)
    if temperature and not extreme:
        score = func.avg(DailyValue.value)
    elif temperature:
        score = func.min(DailyValue.value) if coldest else func.max(DailyValue.value)
    elif period in RAIN_PERIODS:
        score = func.sum(DailyValue.value)
    elif period == "winter_days":
        score = func.count(DailyValue.id).filter(DailyValue.value >= 1)
    else:  # now, winter_max
        score = func.max(DailyValue.value)

    query = (
        select(Station, score.label("score"), counted.label("counted"))
        .join(DailyValue, DailyValue.station_id == Station.id)
        .where(
            Station.active.is_(True),
            DailyValue.parameter == parameter,
            DailyValue.date.between(start, end),
            DailyValue.has_data.is_(True),
            or_(DailyValue.flag.is_(None), DailyValue.flag != SUSPECT_SPATIAL),
        )
        .group_by(Station.id)
    )
    if country is not None:
        query = query.where(Station.country.in_(COUNTRY_CODES[country]))
    # One day's value or an extreme needs no coverage; totals, counts and averages do.
    needs_coverage = not extreme
    if not temperature:
        query = query.having(score > 0)
    if needs_coverage and min_coverage > 0:
        query = query.having(counted >= min_coverage * days)
    query = query.order_by(score.asc() if coldest else score.desc(), Station.name).limit(limit)
    rows = db.execute(query).all()
    on_dates = _extreme_dates(db, parameter, start, end, rows) if extreme and period != "now" else {}

    stations = [
        RankedStation(
            rank=rank,
            id=str(station.id),
            source_station_id=station.source_station_id,
            name=station.name,
            country=station.country,
            source=station.source,
            lat=station.lat,
            lon=station.lon,
            region=station.region,
            owner=station.owner,
            value=round(float(value or 0), 1),
            days_with_data=n,
            days=days,
            coverage=round(n / days, 3),
            on_date=on_dates.get(station.id),
        )
        for rank, (station, value, n) in enumerate(rows, start=1)
    ]
    return RankingsResponse(
        parameter=parameter,
        period=period,
        order=order if temperature else None,
        unit=UNITS[parameter],
        start=start,
        end=end,
        days=days,
        min_coverage=min_coverage if needs_coverage else 0,
        stations=stations,
    )


def _extreme_dates(db: Session, parameter: str, start: date, end: date, rows) -> dict:
    """The (latest) date each ranked station had its score, for extremes like the coldest night."""
    wanted = {station.id: value for station, value, _ in rows}
    if not wanted:
        return {}
    found = db.execute(
        select(DailyValue.station_id, DailyValue.date, DailyValue.value).where(
            DailyValue.station_id.in_(wanted),
            DailyValue.parameter == parameter,
            DailyValue.date.between(start, end),
            DailyValue.has_data.is_(True),
            or_(DailyValue.flag.is_(None), DailyValue.flag != SUSPECT_SPATIAL),
        )
    ).all()
    dates: dict = {}
    for station_id, day, value in found:
        if value == wanted[station_id] and (station_id not in dates or day > dates[station_id]):
            dates[station_id] = day
    return dates

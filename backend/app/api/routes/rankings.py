"""Top N rankings per station for a period ending on a date.

Rainfall: totals for the ISO week, calendar month or year up to the date, or the rolling
last 30 days. Snow depth: the depth on the date, the deepest since 1 October, or the days
with snow cover (>= 1 cm) since 1 October.

Values flagged `suspect_spatial` (far above all neighbours, not confirmed by hourly
readings) count as missing, so they never lift a station in a ranking. By default only
stations with data on at least 90% of the period's days are ranked; min_coverage=0 ranks all.
"""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import SNOW_DEPTH, UNITS, DailyValue, Station
from app.db.session import get_db
from app.qc import SUSPECT_SPATIAL
from app.schemas.station import Parameter

router = APIRouter(prefix="/api", tags=["rankings"])

Period = Literal["week", "month", "year", "last30", "now", "winter_max", "winter_days"]
RAIN_PERIODS = {"week", "month", "year", "last30"}
SNOW_PERIODS = {"now", "winter_max", "winter_days"}
# Filter keys -> station country codes (Svalbard and Jan Mayen count as Norway).
COUNTRY_CODES = {"fi": ["FI"], "no": ["NO", "SJ"], "se": ["SE"], "dk": ["DK"], "gl": ["GL"], "fo": ["FO"], "is": ["IS"]}


class RankedStation(BaseModel):
    rank: int
    id: str
    name: str
    country: str
    source: str
    lat: float
    lon: float
    value: float
    days_with_data: int
    days: int  # days in the period
    coverage: float  # days_with_data / days


class RankingsResponse(BaseModel):
    parameter: Parameter
    period: Period
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


@router.get("/rankings", response_model=RankingsResponse)
def get_rankings(
    period: Period = Query(..., description="Rainfall: week, month, year, last30. Snow depth: now, winter_max, winter_days."),
    date_value: date = Query(..., alias="date", description="Last day of the period."),
    parameter: Parameter = Query("precipitation"),
    country: str | None = Query(None, description="fi, no, se, dk, gl, fo or is; default all."),
    limit: int = Query(15, ge=1, le=100),
    min_coverage: float = Query(0.9, ge=0, le=1, description="Share of the period's days a station needs data on."),
    db: Session = Depends(get_db),
):
    if (parameter == SNOW_DEPTH) != (period in SNOW_PERIODS):
        raise HTTPException(status_code=422, detail=f"Period '{period}' doesn't apply to {parameter}.")
    if country is not None and country not in COUNTRY_CODES:
        raise HTTPException(status_code=422, detail=f"Unknown country '{country}'.")

    start, end = period_range(period, date_value)
    days = (end - start).days + 1
    counted = func.count(DailyValue.id)
    if period in ("week", "month", "year", "last30"):
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
    # The depth on one day or the deepest in winter needs no coverage; totals and day counts do.
    needs_coverage = period not in ("now", "winter_max")
    if needs_coverage and min_coverage > 0:
        query = query.having(counted >= min_coverage * days)
    query = query.order_by(score.desc(), Station.name).limit(limit)

    stations = [
        RankedStation(
            rank=rank,
            id=str(station.id),
            name=station.name,
            country=station.country,
            source=station.source,
            lat=station.lat,
            lon=station.lon,
            value=round(float(value or 0), 1),
            days_with_data=n,
            days=days,
            coverage=round(n / days, 3),
        )
        for rank, (station, value, n) in enumerate(db.execute(query).all(), start=1)
    ]
    return RankingsResponse(
        parameter=parameter,
        period=period,
        unit=UNITS[parameter],
        start=start,
        end=end,
        days=days,
        min_coverage=min_coverage if needs_coverage else 0,
        stations=stations,
    )

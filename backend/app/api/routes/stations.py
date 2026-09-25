from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, extract, func, select
from sqlalchemy.orm import Session

from app.db.models import PRECIPITATION, UNITS, DailyValue, Station
from app.db.session import get_db
from app.schemas.station import (
    DatesResponse,
    HistoryValue,
    LatestDateResponse,
    Parameter,
    StationDay,
    StationHistoryResponse,
    StationsForDateResponse,
    YearsResponse,
)

router = APIRouter(prefix="/api", tags=["stations"])

PARAMETER_QUERY = Query(PRECIPITATION, description="Measurement type: precipitation (mm) or snow_depth (cm).")


def _latest_date(db: Session, parameter: str) -> date | None:
    return db.execute(
        select(func.max(DailyValue.date)).where(DailyValue.parameter == parameter, DailyValue.has_data.is_(True))
    ).scalar()


def _resolve_date(db: Session, date_value: date | None, parameter: str) -> date:
    if date_value is not None:
        return date_value
    latest = _latest_date(db, parameter)
    if latest is None:
        raise HTTPException(status_code=404, detail=f"No {parameter} data available yet.")
    return latest


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
        date=day,
        parameter=parameter,
        value=value,
        unit=UNITS[parameter],
        precipitation_mm=_compat_mm(parameter, value),
        has_data=record.has_data if record else False,
    )


@router.get("/latest-date", response_model=LatestDateResponse)
def get_latest_date(parameter: Parameter = PARAMETER_QUERY, db: Session = Depends(get_db)):
    return LatestDateResponse(date=_resolve_date(db, None, parameter))


@router.get("/stations", response_model=StationsForDateResponse)
def get_stations_for_date(
    date_value: date | None = Query(None, alias="date", description="Defaults to the latest date with data."),
    parameter: Parameter = PARAMETER_QUERY,
    db: Session = Depends(get_db),
):
    day = _resolve_date(db, date_value, parameter)

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


@router.get("/stations/{station_id}", response_model=StationDay)
def get_station_detail(
    station_id: UUID,
    date_value: date | None = Query(None, alias="date", description="Defaults to the latest date with data."),
    parameter: Parameter = PARAMETER_QUERY,
    db: Session = Depends(get_db),
):
    station = db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found.")

    day = _resolve_date(db, date_value, parameter)
    record = db.execute(
        select(DailyValue).where(
            DailyValue.station_id == station_id, DailyValue.parameter == parameter, DailyValue.date == day
        )
    ).scalar_one_or_none()

    return _station_day(station, day, parameter, record)


MAX_HISTORY_DAYS = 366


@router.get("/stations/{station_id}/history", response_model=StationHistoryResponse)
def get_station_history(
    station_id: UUID,
    start: date | None = Query(None, description="Defaults to 29 days before end."),
    end: date | None = Query(None, description="Defaults to the latest date with data."),
    parameter: Parameter = PARAMETER_QUERY,
    db: Session = Depends(get_db),
):
    if db.get(Station, station_id) is None:
        raise HTTPException(status_code=404, detail="Station not found.")

    end = _resolve_date(db, end, parameter)
    start = start or end - timedelta(days=29)
    if start > end:
        raise HTTPException(status_code=422, detail="start must not be after end.")
    if (end - start).days >= MAX_HISTORY_DAYS:
        raise HTTPException(status_code=422, detail=f"Range is limited to {MAX_HISTORY_DAYS} days.")

    rows = db.execute(
        select(DailyValue)
        .where(DailyValue.station_id == station_id, DailyValue.parameter == parameter)
        .where(DailyValue.date.between(start, end))
        .order_by(DailyValue.date.asc())
    ).scalars()

    return StationHistoryResponse(
        station_id=station_id,
        parameter=parameter,
        unit=UNITS[parameter],
        start=start,
        end=end,
        values=[
            HistoryValue(date=r.date, value=r.value, precipitation_mm=_compat_mm(parameter, r.value), has_data=r.has_data)
            for r in rows
        ],
    )


@router.get("/dates", response_model=DatesResponse)
def get_available_dates(
    year: int | None = Query(None, ge=1900, le=2100),
    parameter: Parameter = PARAMETER_QUERY,
    db: Session = Depends(get_db),
):
    query = (
        select(DailyValue.date)
        .where(DailyValue.parameter == parameter, DailyValue.has_data.is_(True))
        .distinct()
        .order_by(DailyValue.date.desc())
    )
    if year is not None:
        query = query.where(DailyValue.date.between(date(year, 1, 1), date(year, 12, 31)))

    return DatesResponse(dates=db.execute(query).scalars().all())


@router.get("/years", response_model=YearsResponse)
def get_available_years(parameter: Parameter = PARAMETER_QUERY, db: Session = Depends(get_db)):
    year = extract("year", DailyValue.date)
    rows = db.execute(
        select(year)
        .where(DailyValue.parameter == parameter, DailyValue.has_data.is_(True))
        .distinct()
        .order_by(year)
    ).scalars().all()
    return YearsResponse(years=[int(y) for y in rows])

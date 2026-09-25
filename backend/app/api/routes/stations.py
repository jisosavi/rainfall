from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, extract, func, select
from sqlalchemy.orm import Session

from app.db.models import DailyPrecipitation, Station
from app.db.session import get_db
from app.schemas.station import (
    DatesResponse,
    LatestDateResponse,
    StationDay,
    StationsForDateResponse,
    YearsResponse,
)

router = APIRouter(prefix="/api", tags=["stations"])


def _latest_date(db: Session) -> date | None:
    return db.execute(
        select(func.max(DailyPrecipitation.date)).where(DailyPrecipitation.has_data.is_(True))
    ).scalar()


def _resolve_date(db: Session, date_value: date | None) -> date:
    if date_value is not None:
        return date_value
    latest = _latest_date(db)
    if latest is None:
        raise HTTPException(status_code=404, detail="No rainfall data available yet.")
    return latest


def _station_day(station: Station, day: date, record: DailyPrecipitation | None) -> StationDay:
    return StationDay(
        id=station.id,
        source_station_id=station.source_station_id,
        name=station.name,
        lat=station.lat,
        lon=station.lon,
        country=station.country,
        region=station.region,
        date=day,
        precipitation_mm=record.precipitation_mm if record else None,
        has_data=record.has_data if record else False,
    )


@router.get("/latest-date", response_model=LatestDateResponse)
def get_latest_date(db: Session = Depends(get_db)):
    latest = _latest_date(db)
    if latest is None:
        raise HTTPException(status_code=404, detail="No rainfall data available yet.")
    return LatestDateResponse(date=latest)


@router.get("/stations", response_model=StationsForDateResponse)
def get_stations_for_date(
    date_value: date | None = Query(None, alias="date", description="Defaults to the latest date with data."),
    db: Session = Depends(get_db),
):
    day = _resolve_date(db, date_value)

    # LEFT JOIN so stations without a row for the day are still returned (drawn as hollow circles).
    rows = db.execute(
        select(Station, DailyPrecipitation)
        .outerjoin(
            DailyPrecipitation,
            and_(DailyPrecipitation.station_id == Station.id, DailyPrecipitation.date == day),
        )
        .where(Station.active.is_(True))
        .order_by(Station.name.asc())
    ).all()

    return StationsForDateResponse(
        date=day,
        stations=[_station_day(station, day, record) for station, record in rows],
    )


@router.get("/stations/{station_id}", response_model=StationDay)
def get_station_detail(
    station_id: UUID,
    date_value: date | None = Query(None, alias="date", description="Defaults to the latest date with data."),
    db: Session = Depends(get_db),
):
    station = db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found.")

    day = _resolve_date(db, date_value)
    record = db.execute(
        select(DailyPrecipitation)
        .where(DailyPrecipitation.station_id == station_id)
        .where(DailyPrecipitation.date == day)
    ).scalar_one_or_none()

    return _station_day(station, day, record)


@router.get("/dates", response_model=DatesResponse)
def get_available_dates(
    year: int | None = Query(None, ge=1900, le=2100),
    db: Session = Depends(get_db),
):
    query = (
        select(DailyPrecipitation.date)
        .where(DailyPrecipitation.has_data.is_(True))
        .distinct()
        .order_by(DailyPrecipitation.date.desc())
    )
    if year is not None:
        query = query.where(DailyPrecipitation.date.between(date(year, 1, 1), date(year, 12, 31)))

    return DatesResponse(dates=db.execute(query).scalars().all())


@router.get("/years", response_model=YearsResponse)
def get_available_years(db: Session = Depends(get_db)):
    year = extract("year", DailyPrecipitation.date)
    rows = db.execute(
        select(year).where(DailyPrecipitation.has_data.is_(True)).distinct().order_by(year)
    ).scalars().all()
    return YearsResponse(years=[int(y) for y in rows])

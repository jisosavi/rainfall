"""Station endpoints (logic in app.services.stations)."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PRECIPITATION, DailyValue, Station
from app.db.session import get_db
from app.schemas.station import (
    DatesResponse,
    LastDataResponse,
    LatestDateResponse,
    Parameter,
    StationDay,
    StationHistoryResponse,
    StationsForDateResponse,
    StatusResponse,
    YearsResponse,
)
from app.services import stations as service

router = APIRouter(prefix="/api", tags=["stations"])

PARAMETER_QUERY = Query(
    PRECIPITATION, description="Measurement: precipitation (mm), snow_depth (cm), temp_mean, temp_min or temp_max (°C)."
)
# Kept for older imports; the limit lives in app.services.stations.
MAX_HISTORY_DAYS = service.MAX_HISTORY_DAYS


@router.get("/latest-date", response_model=LatestDateResponse)
def get_latest_date(parameter: Parameter = PARAMETER_QUERY, db: Session = Depends(get_db)):
    return LatestDateResponse(date=service.resolve_date(db, None, parameter))


@router.get("/stations", response_model=StationsForDateResponse)
def get_stations_for_date(
    date_value: date | None = Query(None, alias="date", description="Defaults to the latest date with data."),
    parameter: Parameter = PARAMETER_QUERY,
    db: Session = Depends(get_db),
):
    return service.stations_for_date(db, date_value, parameter)


@router.get("/stations/{station_id}", response_model=StationDay)
def get_station_detail(
    station_id: UUID,
    date_value: date | None = Query(None, alias="date", description="Defaults to the latest date with data."),
    parameter: Parameter = PARAMETER_QUERY,
    db: Session = Depends(get_db),
):
    return service.station_day(db, station_id, date_value, parameter)


@router.get("/stations/{station_id}/history", response_model=StationHistoryResponse)
def get_station_history(
    station_id: UUID,
    start: date | None = Query(None, description="Defaults to 29 days before end."),
    end: date | None = Query(None, description="Defaults to the latest date with data."),
    parameter: Parameter = PARAMETER_QUERY,
    db: Session = Depends(get_db),
):
    return service.station_history(db, station_id, start, end, parameter)


@router.get("/stations/{station_id}/last-data", response_model=LastDataResponse)
def get_station_last_data(
    station_id: UUID,
    before: date | None = Query(None, description="Latest date to consider (inclusive). Defaults to any date."),
    parameter: Parameter = PARAMETER_QUERY,
    db: Session = Depends(get_db),
):
    """For a station without data on the shown date: when it last had a value."""
    return service.last_data(db, station_id, before, parameter)


@router.get("/dates", response_model=DatesResponse)
def get_available_dates(
    year: int | None = Query(None, ge=1900, le=2100),
    parameter: Parameter = PARAMETER_QUERY,
    db: Session = Depends(get_db),
):
    return DatesResponse(dates=service.available_dates(db, year, parameter))


@router.get("/status", response_model=StatusResponse)
def get_status(db: Session = Depends(get_db)):
    """When data was last fetched, overall and per source."""
    rows = db.execute(
        select(Station.source, func.max(DailyValue.fetched_at)).join(DailyValue).group_by(Station.source)
    ).all()
    sources = {source: fetched for source, fetched in rows if fetched}
    return StatusResponse(updated_at=max(sources.values(), default=None), sources=sources)


@router.get("/years", response_model=YearsResponse)
def get_available_years(parameter: Parameter = PARAMETER_QUERY, db: Session = Depends(get_db)):
    return YearsResponse(years=service.available_years(db, parameter))

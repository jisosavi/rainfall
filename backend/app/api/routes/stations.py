"""Station endpoints (logic in app.services.stations)."""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PRECIPITATION, DailyValue, Station
from app.db.session import get_db
from app.mcp_server.usage import usage_since
from app.schemas.station import (
    DatesResponse,
    McpUsageDay,
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
    today = datetime.now(timezone.utc).date()  # usage is counted per UTC day
    days = {today.isoformat(): "today", (today - timedelta(days=1)).isoformat(): "yesterday"}
    mcp_usage = {label: McpUsageDay() for label in days.values()}
    for row in usage_since(db, today - timedelta(days=1)):
        label = days.get(row.day.isoformat())
        if label:
            day = mcp_usage[label]
            day.calls += row.calls
            day.errors += row.errors
            day.refused += row.refused
            day.by_tool[row.tool] = day.by_tool.get(row.tool, 0) + row.calls
    return StatusResponse(updated_at=max(sources.values(), default=None), sources=sources, mcp_usage=mcp_usage)


@router.get("/years", response_model=YearsResponse)
def get_available_years(parameter: Parameter = PARAMETER_QUERY, db: Session = Depends(get_db)):
    return YearsResponse(years=service.available_years(db, parameter))

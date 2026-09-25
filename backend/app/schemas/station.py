from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Parameter = Literal["precipitation", "snow_depth"]


class StationDay(BaseModel):
    """One station on one date for one measurement type — what the map and panel consume."""

    id: UUID
    source: str
    source_station_id: str
    name: str
    lat: float
    lon: float
    country: str
    region: str | None = None
    owner: str | None = None
    date: date
    parameter: Parameter = "precipitation"
    value: float | None = None
    unit: str = "mm"
    # Same as value for precipitation, None otherwise. Kept for frontends built before `value`.
    precipitation_mm: float | None = None
    has_data: bool
    # Our quality flag, e.g. "suspect_spatial": far above all nearby stations that day.
    flag: str | None = None


class StationsForDateResponse(BaseModel):
    date: date
    parameter: Parameter = "precipitation"
    unit: str = "mm"
    stations: list[StationDay]


class LatestDateResponse(BaseModel):
    date: date


class DatesResponse(BaseModel):
    dates: list[date]


class YearsResponse(BaseModel):
    years: list[int]


class HistoryValue(BaseModel):
    date: date
    value: float | None = None
    # Same as value for precipitation, None otherwise (compatibility, see StationDay).
    precipitation_mm: float | None = None
    has_data: bool
    flag: str | None = None


class StationHistoryResponse(BaseModel):
    station_id: UUID
    parameter: Parameter = "precipitation"
    unit: str = "mm"
    start: date
    end: date
    values: list[HistoryValue]

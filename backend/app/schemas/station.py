from datetime import date
from uuid import UUID

from pydantic import BaseModel


class StationDay(BaseModel):
    """One station on one date — the object the map and detail panel consume."""

    id: UUID
    source_station_id: str
    name: str
    lat: float
    lon: float
    country: str
    region: str | None = None
    date: date
    precipitation_mm: float | None = None
    has_data: bool


class StationsForDateResponse(BaseModel):
    date: date
    stations: list[StationDay]


class LatestDateResponse(BaseModel):
    date: date


class DatesResponse(BaseModel):
    dates: list[date]


class YearsResponse(BaseModel):
    years: list[int]

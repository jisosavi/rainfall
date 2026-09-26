"""Response models of the shared queries in app.services that the REST API didn't have: station
search, coverage, observation series with summaries, day overviews and data freshness. The MCP
tools return these (as structured output)."""

import datetime as dt
from uuid import UUID

from pydantic import BaseModel

from app.schemas.station import Parameter


class Coverage(BaseModel):
    """What a station reports for one measurement."""

    parameter: Parameter
    unit: str
    first_date: dt.date
    last_date: dt.date
    days_with_data: int


class StationSummary(BaseModel):
    id: UUID
    source: str
    source_station_id: str
    name: str
    country: str
    region: str | None = None
    owner: str | None = None
    lat: float
    lon: float
    elevation_m: float | None = None
    distance_km: float | None = None  # from the searched point, when searching near one
    measurements: list[Parameter]  # measurements with data in the last 400 days


class StationInfo(StationSummary):
    coverage: list[Coverage]


class SeriesSummary(BaseModel):
    days: int  # days in the range
    days_with_data: int
    flagged: int  # values marked suspect_spatial (included in values, left out of this summary)
    min: float | None = None
    min_date: dt.date | None = None
    max: float | None = None
    max_date: dt.date | None = None
    mean: float | None = None
    total: float | None = None  # rainfall only
    days_at_least_1: int | None = None  # rainfall: days with >= 1 mm; snow: days with >= 1 cm


class SeriesValue(BaseModel):
    date: dt.date
    value: float | None = None
    has_data: bool
    flag: str | None = None


class ObservationSeries(BaseModel):
    parameter: Parameter
    unit: str
    summary: SeriesSummary
    values: list[SeriesValue]


class Observations(BaseModel):
    station: StationSummary
    start: dt.date
    end: dt.date
    series: list[ObservationSeries]


class RankedValue(BaseModel):
    station_id: UUID
    name: str
    country: str
    value: float
    flag: str | None = None


class DayOverview(BaseModel):
    date: dt.date
    parameter: Parameter
    unit: str
    country: str | None = None  # filter key (fi, no, …), None = all
    stations: int  # stations with a row that day
    reporting: int  # stations with a value
    flagged: int
    min: RankedValue | None = None
    max: RankedValue | None = None
    mean: float | None = None
    median: float | None = None
    highest: list[RankedValue]  # top N, flagged values left out
    lowest: list[RankedValue]  # temperature only: bottom N


class SourceStatus(BaseModel):
    source: str
    last_fetched: dt.datetime | None = None
    latest_date: dict[str, dt.date]  # parameter -> latest date with data


class DataStatus(BaseModel):
    updated_at: dt.datetime | None = None
    sources: list[SourceStatus]

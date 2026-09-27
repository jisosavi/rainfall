"""MCP server: read-only tools over the shared queries (app.services), for Claude connectors
and other agents. Mounted in the FastAPI app at /mcp (Streamable HTTP, JSON responses).

Tools open their own database session and turn NotFoundError / InvalidRequestError into
ToolError, which the client shows the model as a readable error. Every result carries the
CC BY attribution the data licences require.
"""

import datetime as dt
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal, TypeVar
from uuid import UUID

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session as db_session
from app.schemas.queries import DataStatus, DayOverview, Observations, StationInfo, StationSummary
from app.services import overview, rankings, stations
from app.services.errors import InvalidRequestError, NotFoundError
from app.services.rankings import COUNTRY_CODES, RankingsResponse

CONVENTIONS = (Path(__file__).parent / "conventions.md").read_text(encoding="utf-8")
ATTRIBUTION = (
    "Data: FMI, MET Norway, SMHI, DMI, IMO and Keskkonnaagentuur (CC BY 4.0), processed by "
    "Nordic weather observations (https://isosavi.com/test/rainfall/)."
)

Measurement = Literal["precipitation", "snow_depth", "temp_mean", "temp_min", "temp_max"]
Country = Literal["fi", "no", "se", "dk", "gl", "fo", "is", "ee"]
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

INSTRUCTIONS = """Daily weather observations (rainfall, snow depth, mean/min/max temperature) from about
2,800 stations in Finland, Norway (incl. Svalbard), Sweden, Denmark, Greenland, the Faroe Islands,
Iceland and Estonia, from 2025-01-01, updated twice a day.

How to use:
- Find stations with find_stations (near a lat/lon, or by name), then get_observations for their
  daily values and a summary. For a country or area on one day use get_day_overview; for
  "wettest / coldest / deepest snow" questions use get_rankings.
- Check get_data_status for the latest available dates before saying data is missing: yesterday's
  rainfall appears after 06 UTC today, Estonia's a day later, Iceland's 3-4 days later.
- Day D for rainfall is 06 UTC on D to 06 UTC on D+1; temperature min/max run 18 UTC on D-1 to 18 UTC
  on D; the mean is 00-24 UTC. 0 is a real value; has_data=false means missing.
- Values flagged suspect_spatial are unusual for the area: shown, but left out of summaries and rankings.
- Credit the data when you publish it (see each result's attribution). Full rules: resource
  weather://conventions."""

mcp = MCPServer(
    name="nordic-weather",
    title="Nordic weather observations",
    description="Daily rainfall, snow depth and temperature at Nordic and Estonian weather stations.",
    instructions=INSTRUCTIONS,
    website_url="https://isosavi.com/test/rainfall/",
    version="1.0.0",
)


class Attributed(BaseModel):
    attribution: str = ATTRIBUTION


class StationsResult(Attributed):
    stations: list[StationSummary]


class StationResult(StationInfo, Attributed):
    pass


class ObservationsResult(Observations, Attributed):
    pass


class DayOverviewResult(DayOverview, Attributed):
    pass


class RankingsResult(RankingsResponse, Attributed):
    pass


class DataStatusResult(DataStatus, Attributed):
    pass


T = TypeVar("T")


@contextmanager
def _db() -> Iterator[Session]:
    db = db_session.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run(query: Callable[[Session], T]) -> T:
    """Run a shared query; its expected failures become errors the model can read."""
    with _db() as db:
        try:
            return query(db)
        except (NotFoundError, InvalidRequestError) as exc:
            raise ToolError(str(exc)) from exc


@mcp.tool(title="Find weather stations", annotations=READ_ONLY)
def find_stations(
    lat: Annotated[float | None, Field(ge=-90, le=90, description="Latitude of a place to search near.")] = None,
    lon: Annotated[float | None, Field(ge=-180, le=180, description="Longitude of that place.")] = None,
    radius_km: Annotated[float, Field(gt=0, le=500, description="Search radius around lat/lon.")] = 50,
    name: Annotated[str | None, Field(max_length=80, description="Part of a station or municipality name, e.g. 'Helsinki'.")] = None,
    country: Annotated[Country | None, Field(description="Only stations in this country (no includes Svalbard).")] = None,
    measurement: Annotated[Measurement | None, Field(description="Only stations reporting this measurement.")] = None,
    limit: Annotated[int, Field(ge=1, le=20)] = 10,
) -> StationsResult:
    """Find active weather stations near a point (nearest first, with distance) and/or by name.

    Give lat and lon (convert a place name to coordinates yourself), or a name. Each station lists
    the measurements it has reported in the last 400 days, its height and owner. Use the returned
    id with get_station or get_observations."""
    codes = COUNTRY_CODES[country] if country else None
    return StationsResult(
        stations=_run(
            lambda db: stations.find_stations(
                db, lat=lat, lon=lon, radius_km=radius_km, name=name, countries=codes, parameter=measurement, limit=limit
            )
        )
    )


@mcp.tool(title="Station details", annotations=READ_ONLY)
def get_station(station_id: Annotated[UUID, Field(description="Station id from find_stations.")]) -> StationResult:
    """A station's details and, per measurement, the first and last date with data and the number
    of days with data. Use it to see what a station measures and how far back it goes."""
    info = _run(lambda db: stations.station_info(db, station_id))
    return StationResult(**info.model_dump())


@mcp.tool(title="Daily observations", annotations=READ_ONLY)
def get_observations(
    station_id: Annotated[UUID, Field(description="Station id from find_stations.")],
    measurements: Annotated[list[Measurement], Field(min_length=1, max_length=5, description="One or more measurements.")],
    start: Annotated[dt.date | None, Field(description="First date (YYYY-MM-DD). Default: 29 days before end.")] = None,
    end: Annotated[dt.date | None, Field(description="Last date. Default: the latest date with data.")] = None,
    summary_only: Annotated[bool, Field(description="Leave out the daily values, keep the summaries.")] = False,
) -> ObservationsResult:
    """Daily values at one station for up to 366 days, with a summary per measurement: min and max
    (with dates), mean, and for rainfall the total and days with at least 1 mm (snow: days with at
    least 1 cm). Flagged (suspect) values are listed but left out of the summary. Missing days have
    has_data false; a date without a row wasn't reported at all."""
    result = _run(lambda db: stations.observations(db, station_id, list(dict.fromkeys(measurements)), start, end))
    if summary_only:
        for series in result.series:
            series.values = []
    return ObservationsResult(**result.model_dump())


@mcp.tool(title="Day overview", annotations=READ_ONLY)
def get_day_overview(
    measurement: Measurement,
    date: Annotated[dt.date | None, Field(description="YYYY-MM-DD. Default: the latest date with data.")] = None,
    country: Annotated[Country | None, Field(description="Limit to one country.")] = None,
    min_lon: Annotated[float | None, Field(ge=-180, le=180, description="Optional area: west edge.")] = None,
    min_lat: Annotated[float | None, Field(ge=-90, le=90, description="South edge.")] = None,
    max_lon: Annotated[float | None, Field(ge=-180, le=180, description="East edge.")] = None,
    max_lat: Annotated[float | None, Field(ge=-90, le=90, description="North edge.")] = None,
    top: Annotated[int, Field(ge=1, le=25, description="How many stations to list.")] = 10,
) -> DayOverviewResult:
    """One date across a country, an area (all four edges) or everywhere: how many stations
    reported, the extremes, mean and median, and the highest stations (for temperature also the
    lowest). Flagged values are counted but left out of the statistics."""
    edges = (min_lon, min_lat, max_lon, max_lat)
    if any(e is not None for e in edges) and any(e is None for e in edges):
        raise ToolError("Give all four area edges (min_lon, min_lat, max_lon, max_lat), or none.")
    bbox = edges if all(e is not None for e in edges) else None
    result = _run(lambda db: overview.day_overview(db, date, measurement, country=country, bbox=bbox, top=top))
    return DayOverviewResult(**result.model_dump())


@mcp.tool(title="Rankings", annotations=READ_ONLY)
def get_rankings(
    measurement: Measurement,
    period: Annotated[
        Literal["now", "week", "month", "year", "last30", "winter_max", "winter_days"],
        Field(
            description=(
                "Rainfall: week (ISO week to date), month, year, last30 (totals). Snow depth: now (the "
                "date), winter_max (deepest since 1 October), winter_days (days with snow). Temperature: "
                "now, week, month, year, last30."
            )
        ),
    ],
    date: Annotated[dt.date | None, Field(description="Last day of the period. Default: the latest date with data.")] = None,
    order: Annotated[Literal["warmest", "coldest"], Field(description="Temperature only.")] = "warmest",
    country: Country | None = None,
    include_gaps: Annotated[bool, Field(description="Also rank stations with data on under 90% of the days.")] = False,
    limit: Annotated[int, Field(ge=1, le=50)] = 15,
) -> RankingsResult:
    """Top stations for a period ending on a date, as in the app's Top 15: wettest (rain totals),
    deepest snow or most snow days, and warmest or coldest (temperature minimum and maximum rank by
    the period's extreme with the date it happened; the mean by the period's average). Flagged values
    don't count. Rain and snow stations scoring 0 aren't listed."""

    def query(db: Session) -> RankingsResponse:
        day = date or stations.resolve_date(db, None, measurement)
        return rankings.rankings(
            db, period=period, date_value=day, parameter=measurement, country=country,
            limit=limit, min_coverage=0 if include_gaps else 0.9, order=order,
        )

    return RankingsResult(**_run(query).model_dump())


@mcp.tool(title="Data freshness", annotations=READ_ONLY)
def get_data_status() -> DataStatusResult:
    """When each source (fmi Finland, met Norway, smhi Sweden, dmi Denmark/Greenland/Faroe Islands,
    imo Iceland, kaa Estonia) was last fetched, and its latest date with data per measurement."""
    return DataStatusResult(**_run(overview.data_status).model_dump())


@mcp.resource(
    "weather://conventions",
    name="conventions",
    title="Data conventions",
    description="Day windows per measurement and country, missing vs zero, quality flags, licences.",
    mime_type="text/markdown",
)
def conventions() -> str:
    return CONVENTIONS


@mcp.prompt(title="Weather summary", description="Summarise recent weather in a country.")
def weather_summary(country: str, days: str = "7") -> str:
    return (
        f"Summarise the weather of the last {days} days in {country} using the Nordic weather tools: "
        "check get_data_status for the latest dates, then use get_day_overview and get_rankings for "
        "rainfall, temperature (min and max) and, in winter, snow depth. Mention notable extremes with "
        "station names and dates, say which days are still incomplete, and credit the data."
    )


def http_app():
    """The Starlette app serving MCP at /mcp. Stateful sessions (per-session limits need the
    session id); plain JSON responses, as no tool streams."""
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        max_sessions=2000,
        host="0.0.0.0",  # a public server: no localhost-only DNS-rebinding guard
    )


def public_mcp_url() -> str:
    return get_settings().public_base_url.rstrip("/") + "/mcp"

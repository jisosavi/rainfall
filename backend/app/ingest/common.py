"""Shared types for ingestion sources (FMI, MET Norway)."""

from dataclasses import dataclass, field
from datetime import date, timedelta

CHUNK_DAYS = 31


@dataclass(frozen=True)
class Normalized:
    precipitation_mm: float | None
    has_data: bool
    raw_status: str


@dataclass
class StationSeries:
    """One station's daily values, already normalized and dated by our convention:
    a value stored under date D covers 06 UTC on D to 06 UTC on D+1."""

    source: str  # "fmi", "met" or "smhi"
    source_station_id: str
    name: str
    region: str | None
    lat: float
    lon: float
    country: str
    values: list[tuple[date, Normalized]] = field(default_factory=list)
    owner: str | None = None  # organisation running the station, when the source says


def date_chunks(start: date, end: date, days: int = CHUNK_DAYS):
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=days - 1), end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)

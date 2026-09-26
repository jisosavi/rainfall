"""Shared types for ingestion sources (FMI, MET Norway)."""

from dataclasses import dataclass, field
from datetime import date, timedelta

CHUNK_DAYS = 31

# Values outside these are treated as missing, whatever the source's quality flag says. They
# lie well beyond Nordic records (daily rainfall: Finland ~198 mm, Norway ~230 mm; temperature
# about -51 to +35 °C) and catch broken feeds, e.g. SMHI's Söråker reporting 17280 mm a day.
PLAUSIBLE_RANGE = {
    "precipitation": (0.0, 300.0),
    "snow_depth": (0.0, 600.0),
    "temp_mean": (-60.0, 40.0),
    "temp_min": (-60.0, 40.0),
    "temp_max": (-60.0, 40.0),
}
IMPLAUSIBLE = "implausible"


@dataclass(frozen=True)
class Normalized:
    value: float | None  # in the parameter's unit
    has_data: bool
    raw_status: str


@dataclass
class StationSeries:
    """One station's daily values, already normalized and dated by our convention:
    a value stored under date D covers 06 UTC on D to 06 UTC on D+1."""

    source: str  # "fmi", "met", "smhi", "dmi", "imo" or "kaa"
    source_station_id: str
    name: str
    region: str | None
    lat: float
    lon: float
    country: str
    values: list[tuple[date, Normalized]] = field(default_factory=list)
    owner: str | None = None  # organisation running the station, when the source says
    parameter: str = "precipitation"  # measurement type, see app.db.models.PARAMETERS
    elevation_m: float | None = None  # metres above sea level, when known


def check_plausible(parameter: str, value: "Normalized") -> "Normalized":
    """Turn an impossible value into a missing one, keeping the source's raw value."""
    low, high = PLAUSIBLE_RANGE[parameter]
    if value.value is not None and not low <= value.value <= high:
        return Normalized(None, False, f"{value.raw_status}|{IMPLAUSIBLE}"[:64])
    return value


def date_chunks(start: date, end: date, days: int = CHUNK_DAYS):
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=days - 1), end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)

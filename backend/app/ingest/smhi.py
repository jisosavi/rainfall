"""Client for SMHI Open Data Meteorological Observations: daily precipitation (parameter 5,
"Nederbördsmängd, summa 1 dygn, 1 gång/dygn, kl 06").

Facts verified against the live API (2026-09):
- Each value has explicit from/to times and a "representative day" (ref), which is the day
  the 06 UTC window starts: ref D covers 06 UTC on D to 06 UTC on D+1, the same convention
  as FMI, so ref is stored as-is (checked against hourly sums at 5 stations).
- There is no all-stations query for this parameter: data is fetched per station.
  latest-months (JSON) covers about the last 4 months; corrected-archive (CSV) holds
  quality-controlled history up to about 3 months ago and replaces preliminary values.
- Quality: G = checked and approved, Y = suspicious or not yet checked (newest data).
  Both are kept; the flag goes into raw_status.
- Missing days are simply absent, so they are filled in as missing rows.
- Snow depth: parameter 8 ("Snödjup, momentanvärde, 1 gång/dygn, kl 06"), a reading at
  06 UTC, **in metres** (converted to cm). Values carry a timestamp instead of ref, and the
  archive CSV has different columns (Datum; Tid; Snödjup; Kvalitet). Many stations report
  irregularly, so only reported days are stored (no missing rows).
- No registration. Licence CC BY 4.0: credit SMHI and say the data was processed.
"""

import csv
import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx

from app.ingest.common import Normalized, StationSeries

logger = logging.getLogger(__name__)

BASE_URL = "https://opendata-download-metobs.smhi.se/api/version/1.0/parameter"
SOURCE = "smhi"
USER_AGENT = "rainfall github.com/jisosavi/rainfall"
# latest-months reaches back ~4 months; older dates need the corrected archive.
LATEST_MONTHS_DAYS = 110
PARALLEL_REQUESTS = 4
VALID_QUALITIES = {"G", "Y"}


@dataclass(frozen=True)
class _Parameter:
    number: int
    scale: float  # multiply SMHI's value to get our unit
    fill_missing: bool  # add has_data=false rows for unreported days


PARAMETERS = {
    "precipitation": _Parameter(5, scale=1.0, fill_missing=True),  # mm
    "snow_depth": _Parameter(8, scale=100.0, fill_missing=False),  # metres -> cm
}


@dataclass
class _Station:
    id: str
    name: str
    owner: str | None
    lat: float
    lon: float
    elevation_m: float | None
    first_day: date
    last_day: date


def make_client() -> httpx.Client:
    return httpx.Client(timeout=120, headers={"User-Agent": USER_AGENT})


def _ms_to_date(ms: int) -> date:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).date()


def _get(client: httpx.Client, url: str, retries: int = 3) -> httpx.Response | None:
    for attempt in range(1, retries + 1):
        try:
            response = client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            if attempt == retries:
                raise
            wait = 5 * attempt
            logger.warning("SMHI request %s failed (%s), retrying in %ss", url, exc, wait)
            time.sleep(wait)
    return None


def normalize(value: str | None, quality: str | None, scale: float = 1.0) -> Normalized:
    raw = f"{value}|{quality}"
    try:
        number = float(value) if value is not None else None
    except ValueError:
        number = None
    if number is None or number < 0 or quality not in VALID_QUALITIES:
        return Normalized(None, False, raw)
    return Normalized(round(number * scale, 2), True, raw)


def parse_stations(payload: dict, start: date, end: date) -> list[_Station]:
    """Stations whose observation period overlaps start..end."""
    stations = []
    for s in payload.get("station", []):
        first_day, last_day = _ms_to_date(s["from"]), _ms_to_date(s["to"])
        if first_day > end or last_day < start:
            continue
        stations.append(
            _Station(
                id=str(s["id"]),
                name=s["name"].strip(),
                owner=(s.get("owner") or "").strip() or None,
                lat=s["latitude"],
                lon=s["longitude"],
                elevation_m=s.get("height"),
                first_day=first_day,
                last_day=last_day,
            )
        )
    return stations


def parse_latest_months(payload: dict, scale: float = 1.0) -> dict[date, Normalized]:
    """Interval values (rainfall) carry `ref`, the representative day; readings (snow depth)
    carry `date`, a timestamp in ms, whose UTC date is the reading's date."""
    values = {}
    for v in payload.get("value") or []:
        day = date.fromisoformat(v["ref"]) if v.get("ref") else _ms_to_date(v["date"])
        values[day] = normalize(v.get("value"), v.get("quality"), scale)
    return values


def parse_archive_csv(text: str, start: date, scale: float = 1.0) -> dict[date, Normalized]:
    """The CSV has metadata blocks first, then a data header. Interval values (rainfall):
    'Från Datum Tid (UTC); Till …; Representativt dygn; value; quality'. Readings (snow depth):
    'Datum; Tid (UTC); value; quality'. Trailing columns hold free-text notes."""
    lines = text.lstrip("\ufeff").splitlines()
    header = next((i for i, line in enumerate(lines) if line.startswith(("Från Datum Tid", "Datum;"))), None)
    if header is None:
        return {}
    # Column positions of (day, value, quality).
    day_col, value_col, quality_col = (2, 3, 4) if lines[header].startswith("Från") else (0, 2, 3)
    values: dict[date, Normalized] = {}
    for row in csv.reader(io.StringIO("\n".join(lines[header + 1 :])), delimiter=";"):
        if len(row) <= quality_col or not row[day_col]:
            continue
        try:
            day = date.fromisoformat(row[day_col].strip())
        except ValueError:
            continue
        if day >= start:
            values[day] = normalize(row[value_col].strip() or None, row[quality_col].strip() or None, scale)
    return values


def fetch_stations(client: httpx.Client, start: date, end: date, parameter: str = "precipitation") -> list[_Station]:
    response = _get(client, f"{BASE_URL}/{PARAMETERS[parameter].number}.json")
    return parse_stations(response.json(), start, end) if response else []


def _fetch_station_values(
    client: httpx.Client, station: _Station, start: date, use_archive: bool, parameter: str
) -> dict[date, Normalized]:
    config = PARAMETERS[parameter]
    values: dict[date, Normalized] = {}
    base = f"{BASE_URL}/{config.number}/station/{station.id}/period"
    latest = _get(client, f"{base}/latest-months/data.json")
    if latest:
        values.update(parse_latest_months(latest.json(), config.scale))
    if use_archive:
        archive = _get(client, f"{base}/corrected-archive/data.csv")
        if archive:
            # Corrected archive values replace the preliminary latest-months ones.
            values.update(parse_archive_csv(archive.text, start, config.scale))
    return values


def fetch_daily(
    client: httpx.Client,
    start: date,
    end: date,
    stations: list[_Station] | None = None,
    use_archive: bool | None = None,
    today: date | None = None,
    parameter: str = "precipitation",
) -> list[StationSeries]:
    """All stations' values for start..end. The archive is used automatically when start is
    older than latest-months reaches, or when use_archive=True (monthly corrections refresh)."""
    today = today or datetime.now(timezone.utc).date()
    if use_archive is None:
        use_archive = start < today - timedelta(days=LATEST_MONTHS_DAYS)
    config = PARAMETERS[parameter]
    stations = stations if stations is not None else fetch_stations(client, start, end, parameter)

    with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
        all_values = list(pool.map(lambda s: _fetch_station_values(client, s, start, use_archive, parameter), stations))

    result = []
    for station, values in zip(stations, all_values):
        series = StationSeries(
            source=SOURCE,
            source_station_id=station.id,
            name=station.name,
            region=None,
            lat=station.lat,
            lon=station.lon,
            country="SE",
            owner=station.owner,
            parameter=parameter,
            elevation_m=station.elevation_m,
        )
        if config.fill_missing:
            day, last = max(start, station.first_day), min(end, station.last_day)
            while day <= last:
                # A day without an observation becomes an explicit missing row (hollow circle).
                series.values.append((day, values.get(day, Normalized(None, False, "missing"))))
                day += timedelta(days=1)
        else:
            series.values = sorted((d, v) for d, v in values.items() if start <= d <= end)
        if series.values:
            result.append(series)
    return result


def slice_series(series: list[StationSeries], start: date, end: date) -> list[StationSeries]:
    """The part of already-fetched series within start..end, for storing in chunks."""
    out = []
    for s in series:
        values = [(d, v) for d, v in s.values if start <= d <= end]
        if values:
            out.append(
                StationSeries(
                    s.source, s.source_station_id, s.name, s.region, s.lat, s.lon, s.country, values, s.owner, s.parameter,
                    s.elevation_m,
                )
            )
    return out

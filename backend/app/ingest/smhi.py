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

API_URL = "https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/5"
SOURCE = "smhi"
USER_AGENT = "rainfall github.com/jisosavi/rainfall"
# latest-months reaches back ~4 months; older dates need the corrected archive.
LATEST_MONTHS_DAYS = 110
PARALLEL_REQUESTS = 4
VALID_QUALITIES = {"G", "Y"}


@dataclass
class _Station:
    id: str
    name: str
    owner: str | None
    lat: float
    lon: float
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


def normalize(value: str | None, quality: str | None) -> Normalized:
    raw = f"{value}|{quality}"
    try:
        mm = float(value) if value is not None else None
    except ValueError:
        mm = None
    if mm is None or mm < 0 or quality not in VALID_QUALITIES:
        return Normalized(None, False, raw)
    return Normalized(mm, True, raw)


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
                first_day=first_day,
                last_day=last_day,
            )
        )
    return stations


def parse_latest_months(payload: dict) -> dict[date, Normalized]:
    return {date.fromisoformat(v["ref"]): normalize(v.get("value"), v.get("quality")) for v in payload.get("value") or []}


def parse_archive_csv(text: str, start: date) -> dict[date, Normalized]:
    """The CSV has metadata blocks first; data starts after the 'Från Datum Tid (UTC)' header.
    Columns: from; to; representative day; value; quality; (free-text notes)."""
    lines = text.lstrip("﻿").splitlines()
    header = next((i for i, line in enumerate(lines) if line.startswith("Från Datum Tid")), None)
    if header is None:
        return {}
    values: dict[date, Normalized] = {}
    for row in csv.reader(io.StringIO("\n".join(lines[header + 1 :])), delimiter=";"):
        if len(row) < 5 or not row[2]:
            continue
        try:
            day = date.fromisoformat(row[2].strip())
        except ValueError:
            continue
        if day >= start:
            values[day] = normalize(row[3].strip() or None, row[4].strip() or None)
    return values


def fetch_stations(client: httpx.Client, start: date, end: date) -> list[_Station]:
    response = _get(client, f"{API_URL}.json")
    return parse_stations(response.json(), start, end) if response else []


def _fetch_station_values(client: httpx.Client, station: _Station, start: date, use_archive: bool) -> dict[date, Normalized]:
    values: dict[date, Normalized] = {}
    base = f"{API_URL}/station/{station.id}/period"
    latest = _get(client, f"{base}/latest-months/data.json")
    if latest:
        values.update(parse_latest_months(latest.json()))
    if use_archive:
        archive = _get(client, f"{base}/corrected-archive/data.csv")
        if archive:
            # Corrected archive values replace the preliminary latest-months ones.
            values.update(parse_archive_csv(archive.text, start))
    return values


def fetch_daily(
    client: httpx.Client,
    start: date,
    end: date,
    stations: list[_Station] | None = None,
    use_archive: bool | None = None,
    today: date | None = None,
) -> list[StationSeries]:
    """All stations' values for start..end. The archive is used automatically when start is
    older than latest-months reaches, or when use_archive=True (monthly corrections refresh)."""
    today = today or datetime.now(timezone.utc).date()
    if use_archive is None:
        use_archive = start < today - timedelta(days=LATEST_MONTHS_DAYS)
    stations = stations if stations is not None else fetch_stations(client, start, end)

    with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
        all_values = list(pool.map(lambda s: _fetch_station_values(client, s, start, use_archive), stations))

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
        )
        day, last = max(start, station.first_day), min(end, station.last_day)
        while day <= last:
            # A day without an observation becomes an explicit missing row (hollow circle).
            series.values.append((day, values.get(day, Normalized(None, False, "missing"))))
            day += timedelta(days=1)
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
                StationSeries(s.source, s.source_station_id, s.name, s.region, s.lat, s.lon, s.country, values, s.owner)
            )
    return out

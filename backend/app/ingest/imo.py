"""Client for the Icelandic Meteorological Office (IMO / Veðurstofa Íslands) weather API.

Facts verified against the live API (2026-09):
- https://api.vedur.is/weather, no registration or key. Licence CC BY 4.0
  (terms: https://athuganir.vedur.is/disclaimer?lng=en).
- The API has no hourly rainfall (the hourly `r` is always empty), so rainfall can't be
  summed over our 06–06 UTC day. The only daily rainfall is `r09` in the EDR day
  collection: the 24 h total from 09 UTC on D-1 to 09 UTC on D, labelled D (it equals the
  manual stations' own 09 UTC reading on D). It is stored under D-1, whose 06–06 UTC day
  overlaps it by 21 of 24 hours; the 3 h offset is stated in the app. Stations that report
  rainfall in a period get a missing row for each day without a value (hollow circles),
  including the latest 3–4 days, which are published late and filled in by later runs.
- Snow depth comes from manual stations' 09 UTC synop readings (types `ur`, `sk`): `snd` in
  cm. Without `snd`, the observer's snow cover `sncm` = 0 ("No snow") counts as 0 cm; partly
  or fully covered without a depth is unknown and not stored. (`snc` can contradict `sncm`
  and isn't used.) A reading at 09 UTC on D is stored under D. Reported days only.
- Temperature is computed from the EDR hour collection (one parameter per query, at most
  3 days per request or it answers 413): the mean from `t`, the on-the-hour reading, at
  00–23 UTC on D (at least 20 readings); min/max from `tn`/`tx`, each the extreme of the
  past hour (timestamp at its end), over 18 UTC on D-1 to 18 UTC on D (at least 22 hours).
  Stations with temperature in a period get a row for every day of it.
- The API answers 404 when a query has no data.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import httpx

from app.ingest.common import Normalized, StationSeries

logger = logging.getLogger(__name__)

API_URL = "https://api.vedur.is/weather"
SOURCE = "imo"
USER_AGENT = "rainfall github.com/jisosavi/rainfall"
ICELAND_BBOX = "-25,63,-13,67"
MANUAL_TYPES = {"ur", "sk"}  # precipitation stations and staffed synop stations
SYNOP_BATCH = 20
NO_SNOW = 0  # sncm code
HOUR_CHUNK_DAYS = 3  # the hour cube refuses longer requests (413)
TEMP_MEAN_MIN_HOURS = 20
TEMP_EXTREME_MIN_HOURS = 22
TEMPERATURE_CODES = {"temp_mean": "t", "temp_min": "tn", "temp_max": "tx"}


@dataclass
class _Station:
    id: str
    name: str
    owner: str | None
    lat: float
    lon: float
    elevation_m: float | None
    type: str


def make_client() -> httpx.Client:
    return httpx.Client(timeout=300, headers={"User-Agent": USER_AGENT})


def _get(client: httpx.Client, path: str, params: dict, retries: int = 3):
    for attempt in range(1, retries + 1):
        try:
            response = client.get(f"{API_URL}{path}", params=params)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            if attempt == retries:
                raise
            wait = 5 * attempt
            logger.warning("IMO request %s failed (%s), retrying in %ss", path, exc, wait)
            time.sleep(wait)
    return None


def _tidy_owner(owner: str | None) -> str | None:
    """Owners sometimes start with a stray separator: ", Veðurstofa Íslands"."""
    owner = (owner or "").strip().lstrip(",").strip()
    return owner or None


def parse_stations(payload: list[dict]) -> list[_Station]:
    return [
        _Station(
            id=str(s["station"]),
            name=s["name"].strip(),
            owner=_tidy_owner(s.get("owner")),
            lat=s["lat"],
            lon=s["lon"],
            elevation_m=s.get("ele"),
            type=s.get("type") or "",
        )
        for s in payload
        if s.get("lat") is not None and s.get("lon") is not None
    ]


def fetch_stations(client: httpx.Client) -> list[_Station]:
    return parse_stations(_get(client, "/stations", {"active": "true"}) or [])


def parse_r09_cube(payload: dict | None, start: date, end: date) -> dict[str, dict[date, Normalized]]:
    """EDR day coverages -> {station id: {stored date: value}}; label D is stored under D-1."""
    result: dict[str, dict[date, Normalized]] = defaultdict(dict)
    for coverage in (payload or {}).get("coverages", []):
        times = coverage["domain"]["axes"]["t"]["values"]
        values = (coverage.get("ranges") or {}).get("r09", {}).get("values", [])
        for label, value in zip(times, values):
            if value is None:
                continue
            day = date.fromisoformat(label[:10]) - timedelta(days=1)
            if start <= day <= end:
                if value >= 0:
                    result[coverage["id"]][day] = Normalized(float(value), True, f"{value}|r09")
                else:
                    result[coverage["id"]][day] = Normalized(None, False, f"{value}|r09")
    return result


def parse_synop_snow(records: list[dict] | None, start: date, end: date) -> dict[str, dict[date, Normalized]]:
    """09 UTC synop readings -> {station id: {date: snow depth}}."""
    result: dict[str, dict[date, Normalized]] = defaultdict(dict)
    for record in records or []:
        if record.get("hour") != 9:
            continue
        day = datetime.fromisoformat(record["time"]).date()
        if not start <= day <= end:
            continue
        depth, cover = record.get("snd"), record.get("sncm")
        if depth is not None and depth >= 0:
            result[str(record["station"])][day] = Normalized(float(depth), True, f"{depth}|snd")
        elif cover == NO_SNOW:
            result[str(record["station"])][day] = Normalized(0.0, True, "0|sncm0")
    return result


def parse_hourly_temperature(
    payloads: list[dict | None], start: date, end: date, parameter: str
) -> dict[str, dict[date, Normalized]]:
    """EDR hour coverages -> {station id: {date: daily mean, minimum or maximum}}."""
    code = TEMPERATURE_CODES[parameter]
    # Mean: readings at 00–23 UTC on D. Min/max: hours ending 19 UTC on D-1 to 18 UTC on D.
    shift = timedelta(0) if parameter == "temp_mean" else timedelta(hours=5)
    min_hours = TEMP_MEAN_MIN_HOURS if parameter == "temp_mean" else TEMP_EXTREME_MIN_HOURS
    hours: dict[tuple[str, date], dict[str, float]] = defaultdict(dict)
    for payload in payloads:
        for coverage in (payload or {}).get("coverages", []):
            times = coverage["domain"]["axes"]["t"]["values"]
            values = (coverage.get("ranges") or {}).get(code, {}).get("values", [])
            for label, value in zip(times, values):
                if value is None:
                    continue
                stamp = datetime.fromisoformat(label.replace("Z", "+00:00"))
                day = (stamp + shift).date()
                if start <= day <= end:
                    hours[(coverage["id"], day)][label] = float(value)
    aggregate = {"temp_mean": lambda v: sum(v) / len(v), "temp_min": min, "temp_max": max}[parameter]
    result: dict[str, dict[date, Normalized]] = defaultdict(dict)
    for (station_id, day), by_hour in hours.items():
        readings = list(by_hour.values())
        if len(readings) >= min_hours:
            value = round(aggregate(readings), 1)
            result[station_id][day] = Normalized(value, True, f"{value}|hourly{min(len(readings), 24)}")
        else:
            result[station_id][day] = Normalized(None, False, f"hourly{len(readings)}")
    return result


def _fetch_hour_cube(client: httpx.Client, start: date, end: date, code: str) -> list[dict | None]:
    """Hourly values for days start..end (00–23 UTC), in chunks the API accepts."""
    payloads = []
    day = start
    while day <= end:
        chunk_end = min(day + timedelta(days=HOUR_CHUNK_DAYS - 1), end)
        payloads.append(
            _get(
                client,
                "/rodeo/collections/hour/cube",
                {
                    "bbox": ICELAND_BBOX,
                    "datetime": f"{day}T00:00:00Z/{chunk_end}T23:00:00Z",
                    "parameter-name": code,
                },
            )
        )
        day = chunk_end + timedelta(days=1)
    return payloads


def fetch_daily(
    client: httpx.Client,
    start: date,
    end: date,
    stations: list[_Station] | None = None,
    parameter: str = "precipitation",
) -> list[StationSeries]:
    stations = stations if stations is not None else fetch_stations(client)
    if parameter in TEMPERATURE_CODES:
        # Min/max need the evening of the day before start.
        payloads = _fetch_hour_cube(client, start - timedelta(days=1), end, TEMPERATURE_CODES[parameter])
        by_station = parse_hourly_temperature(payloads, start, end, parameter)
    elif parameter == "precipitation":
        # Labels D+1 cover our stored date D; EDR's end date is inclusive.
        payload = _get(
            client,
            "/rodeo/collections/day/cube",
            {
                "bbox": ICELAND_BBOX,
                "datetime": f"{start + timedelta(days=1)}T00:00:00Z/{end + timedelta(days=1)}T00:00:00Z",
                "parameter-name": "r09",
            },
        )
        by_station = parse_r09_cube(payload, start, end)
    else:
        manual = [s for s in stations if s.type in MANUAL_TYPES]
        records: list[dict] = []
        for i in range(0, len(manual), SYNOP_BATCH):
            records += _get(
                client,
                "/observations/synop",
                {
                    "station_id": [s.id for s in manual[i : i + SYNOP_BATCH]],
                    "parameters": "all",
                    "format": "json",
                    "day_from": start.isoformat(),
                    "day_to": end.isoformat(),
                },
            ) or []
        by_station = parse_synop_snow(records, start, end)

    result = []
    for s in stations:
        values = by_station.get(s.id)
        if not values:
            continue
        if parameter != "snow_depth":
            # Every day in range: a missing row where the station has no value (yet).
            day = start
            while day <= end:
                values.setdefault(day, Normalized(None, False, "missing"))
                day += timedelta(days=1)
        result.append(
            StationSeries(
                source=SOURCE,
                source_station_id=s.id,
                name=s.name,
                region=None,
                lat=s.lat,
                lon=s.lon,
                country="IS",
                values=sorted(values.items()),
                owner=s.owner,
                parameter=parameter,
                elevation_m=s.elevation_m,
            )
        )
    return result

"""Client for the Icelandic Meteorological Office (IMO / Veðurstofa Íslands) weather API.

Facts verified against the live API (2026-09):
- https://api.vedur.is/weather, no registration or key. Licence CC BY 4.0
  (terms: https://athuganir.vedur.is/disclaimer?lng=en).
- The API has no hourly rainfall (the hourly `r` is always empty), so rainfall can't be
  summed over our 06–06 UTC day. The only daily rainfall is `r09` in the EDR day
  collection: the 24 h total from 09 UTC on D-1 to 09 UTC on D, labelled D (it equals the
  manual stations' own 09 UTC reading on D). It is stored under D-1, whose 06–06 UTC day
  overlaps it by 21 of 24 hours; the 3 h offset is stated in the app.
- Snow depth comes from manual stations' 09 UTC synop readings (types `ur`, `sk`): `snd` in
  cm. Without `snd`, the observer's snow cover `sncm` = 0 ("No snow") counts as 0 cm; partly
  or fully covered without a depth is unknown and not stored. (`snc` can contradict `sncm`
  and isn't used.) A reading at 09 UTC on D is stored under D. Reported days only.
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


def fetch_daily(
    client: httpx.Client,
    start: date,
    end: date,
    stations: list[_Station] | None = None,
    parameter: str = "precipitation",
) -> list[StationSeries]:
    stations = stations if stations is not None else fetch_stations(client)
    if parameter == "precipitation":
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

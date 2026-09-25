"""Client for MET Norway's Frost API: daily precipitation, sum(precipitation_amount P1D).

Facts verified against the live API (2026-09):
- Frost labels a daily value by the day its 24 h window ENDS: label D with timeOffset
  PT6H covers 06 UTC on D-1 to 06 UTC on D (checked against hourly sums at 5 stations).
  FMI labels by the day the window starts, so we store Frost's label D under D-1.
- Only PT6H series are used; PT18H series cover a different 24 h window.
- Frost lists foreign stations too; we keep countryCode NO (mainland) and SJ (Svalbard,
  Jan Mayen).
- Frost already converts "no precipitation" (-1) to 0.0. It has no missing-value marker:
  a day without an observation is simply absent, so missing rows are filled in here.
- Frost answers 404 when a query has no data.
- Needs a client ID (HTTP basic auth, empty password). Open data: NLOD 2.0 / CC BY 4.0.
"""

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta

import httpx

from app.ingest.common import Normalized, StationSeries

logger = logging.getLogger(__name__)

FROST_URL = "https://frost.met.no"
ELEMENT = "sum(precipitation_amount P1D)"
TIME_OFFSET = "PT6H"
COUNTRIES = {"NO", "SJ"}
SOURCE = "met"
STATIONS_PER_REQUEST = 100
# Frost quality codes 0-4 are usable; 5 and above are suspicious or erroneous.
MAX_QUALITY_CODE = 4
USER_AGENT = "rainfall github.com/jisosavi/rainfall"


@dataclass
class _Station:
    id: str
    name: str
    region: str | None
    lat: float
    lon: float
    country: str
    owner: str | None
    valid_from: date
    valid_to: date | None


def make_client(client_id: str) -> httpx.Client:
    return httpx.Client(auth=(client_id, ""), timeout=120, headers={"User-Agent": USER_AGENT})


def _tidy(text: str | None) -> str | None:
    """Frost names are upper case ("HVALER - BREKKE"); show them as "Hvaler - Brekke"."""
    return text.strip().title() if text and text.strip() else None


def _label_to_stored(label: date) -> date:
    return label - timedelta(days=1)


def _get(client: httpx.Client, path: str, params: dict, retries: int = 3) -> list[dict]:
    for attempt in range(1, retries + 1):
        try:
            response = client.get(FROST_URL + path, params=params)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            return response.json().get("data", [])
        except httpx.HTTPError as exc:
            if attempt == retries:
                raise
            wait = 5 * attempt
            logger.warning("Frost request %s failed (%s), retrying in %ss", path, exc, wait)
            time.sleep(wait)
    return []


def parse_quality(observation: dict) -> Normalized:
    value = observation.get("value")
    quality = observation.get("qualityCode")
    raw = f"{value}" + (f"|q{quality}" if quality is not None else "")
    if value is None or value < 0 or (quality is not None and quality > MAX_QUALITY_CODE):
        return Normalized(None, False, raw)
    return Normalized(float(value), True, raw)


def fetch_stations(client: httpx.Client, start: date, end: date) -> list[_Station]:
    """Stations with a PT6H daily precipitation series overlapping start..end (stored dates)."""
    series = _get(
        client,
        "/observations/availableTimeSeries/v0.jsonld",
        {
            "elements": ELEMENT,
            "timeoffsets": TIME_OFFSET,
            "referencetime": f"{start + timedelta(days=1)}/{end + timedelta(days=2)}",
        },
    )
    validity: dict[str, tuple[date, date | None]] = {}
    for s in series:
        station_id = s["sourceId"].split(":")[0]
        valid_from = date.fromisoformat(s["validFrom"][:10])
        valid_to = date.fromisoformat(s["validTo"][:10]) if s.get("validTo") else None
        if station_id in validity:  # several series for one station: take the widest span
            old_from, old_to = validity[station_id]
            valid_from = min(valid_from, old_from)
            valid_to = None if valid_to is None or old_to is None else max(valid_to, old_to)
        validity[station_id] = (valid_from, valid_to)

    ids = sorted(validity)
    stations: list[_Station] = []
    for i in range(0, len(ids), STATIONS_PER_REQUEST):
        for meta in _get(client, "/sources/v0.jsonld", {"ids": ",".join(ids[i : i + STATIONS_PER_REQUEST])}):
            coords = (meta.get("geometry") or {}).get("coordinates")
            if meta.get("countryCode") not in COUNTRIES or not coords or not meta.get("name"):
                continue
            valid_from, valid_to = validity[meta["id"]]
            stations.append(
                _Station(
                    id=meta["id"],
                    name=_tidy(meta["name"]),
                    region=_tidy(meta.get("municipality")) or _tidy(meta.get("county")),
                    lat=coords[1],
                    lon=coords[0],
                    country=meta["countryCode"],
                    owner=", ".join(meta.get("stationHolders") or []) or None,
                    valid_from=_label_to_stored(valid_from),
                    valid_to=_label_to_stored(valid_to) if valid_to else None,
                )
            )
    return stations


def fetch_values(client: httpx.Client, station_ids: list[str], start: date, end: date) -> dict[str, dict[date, Normalized]]:
    """Values for stored dates start..end, keyed by station id and stored date."""
    first_label, last_label = start + timedelta(days=1), end + timedelta(days=1)
    items = _get(
        client,
        "/observations/v0.jsonld",
        {
            "sources": ",".join(station_ids),
            "elements": ELEMENT,
            "timeoffsets": TIME_OFFSET,
            "referencetime": f"{first_label}/{last_label + timedelta(days=1)}",
        },
    )
    values: dict[str, dict[date, Normalized]] = {}
    for item in items:
        label = date.fromisoformat(item["referenceTime"][:10])
        if not first_label <= label <= last_label:
            continue
        station_id = item["sourceId"].split(":")[0]
        # Prefer time series 0 when a station has several.
        observations = sorted(item.get("observations", []), key=lambda o: o.get("timeSeriesId", 0))
        if observations:
            values.setdefault(station_id, {}).setdefault(_label_to_stored(label), parse_quality(observations[0]))
    return values


def fetch_daily(client: httpx.Client, start: date, end: date, stations: list[_Station] | None = None) -> list[StationSeries]:
    stations = stations if stations is not None else fetch_stations(client, start, end)
    active = [s for s in stations if s.valid_from <= end and (s.valid_to is None or s.valid_to >= start)]

    result: list[StationSeries] = []
    for i in range(0, len(active), STATIONS_PER_REQUEST):
        batch = active[i : i + STATIONS_PER_REQUEST]
        values = fetch_values(client, [s.id for s in batch], start, end)
        for s in batch:
            series = StationSeries(
                source=SOURCE,
                source_station_id=s.id,
                name=s.name,
                region=s.region,
                lat=s.lat,
                lon=s.lon,
                country=s.country,
                owner=s.owner,
            )
            station_values = values.get(s.id, {})
            day = max(start, s.valid_from)
            last = min(end, s.valid_to) if s.valid_to else end
            while day <= last:
                # A day without an observation becomes an explicit missing row (hollow circle).
                series.values.append((day, station_values.get(day, Normalized(None, False, "missing"))))
                day += timedelta(days=1)
            if series.values:
                result.append(series)
    return result

"""Client for DMI's open data (climateData API): Denmark, Greenland and the Faroe Islands.

Facts verified against the live API (2026-09):
- No registration or key (since 2 December 2025). Fair use: 500 requests per 5 s.
  Licence CC BY 4.0: credit DMI, link the licence, say the data was processed.
- Every value has explicit `from`/`to` times, but DMI's *daily* rainfall can't be used for
  our day: mainland Danish stations cover the local calendar day (e.g. 22–22 UTC in
  summer), and the labels aren't reliable either: Faroese daily values labelled 06–06 UTC
  equal the hourly sum over 00–24 UTC (checked for Tórshavn, Sept 2026), while Greenland's
  match 06–06 UTC. So rainfall for our day D (06 UTC on D to 06 UTC on D+1) is always the
  sum of the hourly `acc_precip` values. Gaps are scattered outages, not a pattern, so a
  day with 23 of 24 hours counts (raw_status `hourly23`); with 22 or fewer it is missing.
  Stations with no hourly data in a period (e.g. Greenland's inactive manual stations)
  get no rows for it, so they don't show as permanently hollow circles.
- Snow depth (`snow_depth`, cm) is daily, from 06 UTC on D, Denmark only (mostly manual
  stations). Only reported days are stored.
- Temperature: DMI's daily values cover Danish local days, so ours are computed from the
  hourly `mean_temp`, `min_temp` and `max_temp_w_date`. Mean: the average of the 24
  hourly means starting 00–23 UTC on D (at least 20 hours). Min/max: the lowest hourly
  minimum / highest hourly maximum over 18 UTC on D-1 to 18 UTC on D (at least 22 hours).
  Every day in range gets a row (missing when too many hours lack data).
- Countries: DNK -> DK, GRL -> GL, FRO -> FO. The station list gives owner and height.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx

from app.ingest.common import Normalized, StationSeries

logger = logging.getLogger(__name__)

API_URL = "https://opendataapi.dmi.dk/v2/climateData/collections"
SOURCE = "dmi"
USER_AGENT = "rainfall github.com/jisosavi/rainfall"
COUNTRIES = {"DNK": "DK", "GRL": "GL", "FRO": "FO"}
PAGE_LIMIT = 300000
HOURS_PER_DAY = 24
MIN_HOURS = 23  # one missing hour is accepted
TEMP_MEAN_MIN_HOURS = 20
TEMP_EXTREME_MIN_HOURS = 22

# Our parameter -> DMI parameterId.
PARAMETER_IDS = {
    "precipitation": "acc_precip",
    "snow_depth": "snow_depth",
    "temp_mean": "mean_temp",
    "temp_min": "min_temp",
    "temp_max": "max_temp_w_date",
}
TEMPERATURES = ("temp_mean", "temp_min", "temp_max")


@dataclass
class _Station:
    id: str
    name: str
    owner: str | None
    lat: float
    lon: float
    country: str
    elevation_m: float | None
    parameters: set[str]


def make_client() -> httpx.Client:
    return httpx.Client(timeout=180, headers={"User-Agent": USER_AGENT})


def _utc(day: date, hour: int = 6) -> str:
    return f"{day.isoformat()}T{hour:02d}:00:00Z"


def _get_features(client: httpx.Client, path: str, params: dict, retries: int = 3) -> list[dict]:
    """All features of a query, following `next` links."""
    features: list[dict] = []
    url, query = f"{API_URL}{path}", {**params, "limit": PAGE_LIMIT}
    while url:
        for attempt in range(1, retries + 1):
            try:
                response = client.get(url, params=query)
                if response.status_code == 404:
                    return features
                response.raise_for_status()
                break
            except httpx.HTTPError as exc:
                if attempt == retries:
                    raise
                wait = 5 * attempt
                logger.warning("DMI request %s failed (%s), retrying in %ss", path, exc, wait)
                time.sleep(wait)
        payload = response.json()
        features += payload.get("features", [])
        url = next((link["href"] for link in payload.get("links", []) if link.get("rel") == "next"), None)
        query = None  # the next link carries its own query string
    return features


def parse_stations(features: list[dict], start: date, end: date) -> list[_Station]:
    """One entry per station: the newest record whose validity overlaps start..end."""
    newest: dict[str, dict] = {}
    for feature in features:
        p = feature["properties"]
        if p.get("country") not in COUNTRIES or not feature.get("geometry"):
            continue
        valid_to = (p.get("operationTo") or p.get("validTo") or "9999")[:10]
        valid_from = (p.get("operationFrom") or p.get("validFrom") or "0000")[:10]
        if valid_to < start.isoformat() or valid_from > end.isoformat():
            continue
        current = newest.get(p["stationId"])
        if current is None or (p.get("validFrom") or "") > (current["properties"].get("validFrom") or ""):
            newest[p["stationId"]] = feature
    stations = []
    for station_id, feature in newest.items():
        p = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"][:2]
        stations.append(
            _Station(
                id=station_id,
                name=p["name"].strip(),
                owner=(p.get("owner") or "").strip() or None,
                lat=lat,
                lon=lon,
                country=COUNTRIES[p["country"]],
                elevation_m=p.get("stationHeight"),
                parameters=set(p.get("parameterId") or []),
            )
        )
    return stations


def fetch_stations(client: httpx.Client, start: date, end: date, parameter: str = "precipitation") -> list[_Station]:
    features = _get_features(client, "/station/items", {})
    return [s for s in parse_stations(features, start, end) if PARAMETER_IDS[parameter] in s.parameters]


def _valid(p: dict) -> bool:
    return p.get("validity", True) is not False and p.get("value") is not None


def daily_from_hours(features: list[dict], start: date, end: date) -> dict[str, dict[date, Normalized]]:
    """Sum hourly rainfall into our days (06–06 UTC). A day with fewer than MIN_HOURS valid
    hours is returned as missing (raw_status notes how many hours there were)."""
    # Keyed by the hour's start, so a duplicated hour is counted once.
    hours: dict[tuple[str, date], dict[datetime, float]] = defaultdict(dict)
    for feature in features:
        p = feature["properties"]
        if not _valid(p):
            continue
        begins = datetime.fromisoformat(p["from"]).astimezone(timezone.utc)
        day = (begins - timedelta(hours=6)).date()  # the hour 06–07 UTC on D starts day D
        if start <= day <= end:
            hours[(p["stationId"], day)][begins] = float(p["value"])
    result: dict[str, dict[date, Normalized]] = defaultdict(dict)
    for (station_id, day), by_hour in hours.items():
        values = list(by_hour.values())
        if len(values) >= MIN_HOURS:
            total = round(sum(values), 2)
            result[station_id][day] = Normalized(total, total >= 0, f"{total}|hourly{min(len(values), HOURS_PER_DAY)}")
        else:
            result[station_id][day] = Normalized(None, False, f"hourly{len(values)}")
    return result


def temperature_from_hours(
    features: list[dict], start: date, end: date, parameter: str
) -> dict[str, dict[date, Normalized]]:
    """Aggregate hourly temperatures into our days: the mean over hours starting 00–23 UTC
    on D, the minimum/maximum over hours starting 18 UTC on D-1 to 17 UTC on D."""
    shift = timedelta(0) if parameter == "temp_mean" else timedelta(hours=-6)
    min_hours = TEMP_MEAN_MIN_HOURS if parameter == "temp_mean" else TEMP_EXTREME_MIN_HOURS
    hours: dict[tuple[str, date], dict[datetime, float]] = defaultdict(dict)
    for feature in features:
        p = feature["properties"]
        if not _valid(p):
            continue
        begins = datetime.fromisoformat(p["from"]).astimezone(timezone.utc)
        day = (begins - shift).date()  # e.g. the hour 18–19 UTC on D-1 is the first of D's min/max
        if start <= day <= end:
            hours[(p["stationId"], day)][begins] = float(p["value"])
    aggregate = {"temp_mean": lambda v: sum(v) / len(v), "temp_min": min, "temp_max": max}[parameter]
    result: dict[str, dict[date, Normalized]] = defaultdict(dict)
    for (station_id, day), by_hour in hours.items():
        values = list(by_hour.values())
        if len(values) >= min_hours:
            value = round(aggregate(values), 1)
            result[station_id][day] = Normalized(value, True, f"{value}|hourly{min(len(values), HOURS_PER_DAY)}")
        else:
            result[station_id][day] = Normalized(None, False, f"hourly{len(values)}")
    return result


def daily_06_utc(features: list[dict], start: date, end: date) -> dict[str, dict[date, Normalized]]:
    """DMI daily values labelled 06 UTC on D to 06 UTC on D+1. Used for snow depth, a single
    06 UTC reading, where the label is reliable; not for rainfall totals (see above)."""
    result: dict[str, dict[date, Normalized]] = defaultdict(dict)
    for feature in features:
        p = feature["properties"]
        begins = datetime.fromisoformat(p["from"]).astimezone(timezone.utc)
        ends = datetime.fromisoformat(p["to"]).astimezone(timezone.utc)
        if (begins.hour, begins.minute) != (6, 0) or ends - begins != timedelta(days=1):
            continue
        day = begins.date()
        if not start <= day <= end:
            continue
        if _valid(p) and float(p["value"]) >= 0:
            result[p["stationId"]][day] = Normalized(float(p["value"]), True, f"{p['value']}|daily")
        else:
            result[p["stationId"]][day] = Normalized(None, False, f"{p.get('value')}|daily-invalid")
    return result


def fetch_daily(
    client: httpx.Client,
    start: date,
    end: date,
    stations: list[_Station] | None = None,
    parameter: str = "precipitation",
) -> list[StationSeries]:
    stations = stations if stations is not None else fetch_stations(client, start, end, parameter)
    parameter_id = PARAMETER_IDS[parameter]
    if parameter in TEMPERATURES:
        window = f"{_utc(start - timedelta(days=1), 18)}/{_utc(end + timedelta(days=1), 0)}"
    else:
        window = f"{_utc(start)}/{_utc(end + timedelta(days=1))}"
    resolution = "day" if parameter == "snow_depth" else "hour"
    features = _get_features(
        client, "/stationValue/items", {"parameterId": parameter_id, "timeResolution": resolution, "datetime": window}
    )
    if parameter == "precipitation":
        by_station = daily_from_hours(features, start, end)
    elif parameter in TEMPERATURES:
        by_station = temperature_from_hours(features, start, end, parameter)
    else:
        by_station = daily_06_utc(features, start, end)

    result = []
    for s in stations:
        series = StationSeries(
            source=SOURCE,
            source_station_id=s.id,
            name=s.name,
            region=None,
            lat=s.lat,
            lon=s.lon,
            country=s.country,
            owner=s.owner,
            parameter=parameter,
            elevation_m=s.elevation_m,
        )
        values = by_station.get(s.id, {})
        if not values:
            continue  # no data from this station in the period
        if parameter != "snow_depth":
            # Every day in range; without enough hours a day is missing (hollow circle).
            day = start
            while day <= end:
                series.values.append((day, values.get(day, Normalized(None, False, "missing"))))
                day += timedelta(days=1)
        else:
            # Snow depth: reported days only.
            series.values = sorted(values.items())
        if series.values:
            result.append(series)
    return result


def fetch_hourly_precipitation(client: httpx.Client, station_id: str, day: date) -> list[float]:
    """Hourly rainfall for our day D at one station, to confirm unusually high values."""
    features = _get_features(
        client,
        "/stationValue/items",
        {
            "stationId": station_id,
            "parameterId": "acc_precip",
            "timeResolution": "hour",
            "datetime": f"{_utc(day)}/{_utc(day + timedelta(days=1))}",
        },
    )
    return [float(f["properties"]["value"]) for f in features if _valid(f["properties"])]

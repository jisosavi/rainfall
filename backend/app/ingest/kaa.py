"""Client for the Estonian Environment Agency (Keskkonnaagentuur, KAA) climate open data.

Facts verified against the live API (2026-09):
- https://keskkonnaandmed.envir.ee, a PostgREST API: no registration or key. Licence
  CC BY 4.0 (https://keskkonnaportaal.ee/et/avaandmed/kliimaandmestik); credit the agency.
- Tables `f_kliima_paev` (daily) and `f_kliima_tund` (hourly) hold one row per station,
  element and time, with the time split into `aasta`, `kuu`, `paev` (and `tund`). Hourly
  times are UTC (the warmest summer hour is 12, i.e. 15 local time); for hourly sums and
  extremes the time marks the end of the hour. `f_kliima_jaam_vaatlus` lists each station's
  elements with coordinates and height. 25 weather stations.
- Data arrives once a day, about 02 UTC, up to 23 UTC the day before.
- Rainfall: the daily `DPREC` covers 18 UTC on D-1 to 18 UTC on D (68/68 days equal the
  hourly sums), so ours is summed from hourly `PR1H` over 06 UTC on D to 06 UTC on D+1,
  like DMI (23 of 24 hours needed). Day D is therefore complete only after the data of
  D+1 arrives, one day later than the other countries.
- Temperature: daily `DTAN`/`DTAX` cover 18 UTC on D-1 to 18 UTC on D (91/91 days equal
  the hourly extremes), stored as-is. The daily mean `DTA08` follows another day, so ours
  is the mean of the hourly `TA` readings at 00–23 UTC (at least 20).
- Snow depth: daily `DSND` (cm), read at 06 UTC on D, reported every day including 0.
- The agency validates its data yearly (first quarter); corrections then aren't picked up
  by the 10-day re-fetch (see roadmap).
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import httpx

from app.ingest.common import Normalized, StationSeries

logger = logging.getLogger(__name__)

API_URL = "https://keskkonnaandmed.envir.ee"
SOURCE = "kaa"
OWNER = "Keskkonnaagentuur"
USER_AGENT = "rainfall github.com/jisosavi/rainfall"
PAGE_SIZE = 20000
MIN_RAIN_HOURS = 23
TEMP_MEAN_MIN_HOURS = 20

# Our parameter -> (table, element code).
ELEMENTS = {
    "precipitation": ("f_kliima_tund", "PR1H"),
    "snow_depth": ("f_kliima_paev", "DSND"),
    "temp_mean": ("f_kliima_tund", "TA"),
    "temp_min": ("f_kliima_paev", "DTAN"),
    "temp_max": ("f_kliima_paev", "DTAX"),
}


@dataclass
class _Station:
    id: str
    name: str
    lat: float
    lon: float
    elevation_m: float | None
    # Element code -> observation periods (from, to); an element can have several, e.g.
    # snow depth one per season.
    elements: dict[str, list[tuple[date, date | None]]]


def make_client() -> httpx.Client:
    return httpx.Client(timeout=180, headers={"User-Agent": USER_AGENT})


def _get_all(client: httpx.Client, table: str, params: dict, retries: int = 3) -> list[dict]:
    """Every row of a query, a page at a time."""
    rows: list[dict] = []
    offset = 0
    while True:
        query = {**params, "limit": PAGE_SIZE, "offset": offset}
        for attempt in range(1, retries + 1):
            try:
                response = client.get(f"{API_URL}/{table}", params=query)
                response.raise_for_status()
                page = response.json()
                break
            except (httpx.HTTPError, ValueError) as exc:
                if attempt == retries:
                    raise
                wait = 5 * attempt
                logger.warning("KAA request %s failed (%s), retrying in %ss", table, exc, wait)
                time.sleep(wait)
        rows += page
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def parse_stations(rows: list[dict]) -> list[_Station]:
    stations: dict[str, _Station] = {}
    for r in rows:
        if r.get("laiuskraad") is None or r.get("pikkuskraad") is None:
            continue
        s = stations.setdefault(
            r["jaam_kood"],
            _Station(
                id=r["jaam_kood"],
                name=(r.get("jaam_nimi") or r["jaam_kood"]).strip(),
                lat=float(r["laiuskraad"]),
                lon=float(r["pikkuskraad"]),
                elevation_m=float(r["korgus_merepinnast_m"]) if r.get("korgus_merepinnast_m") is not None else None,
                elements={},
            ),
        )
        s.elements.setdefault(r["element_kood"], []).append(
            (_day(r.get("vaatlus_periood_algus")) or date.min, _day(r.get("vaatlus_periood_lopp")))
        )
    return list(stations.values())


def fetch_stations(client: httpx.Client) -> list[_Station]:
    codes = ",".join(code for _, code in ELEMENTS.values())
    rows = _get_all(
        client,
        "f_kliima_jaam_vaatlus",
        {
            "select": "jaam_kood,jaam_nimi,laiuskraad,pikkuskraad,korgus_merepinnast_m,element_kood,vaatlus_periood_algus,vaatlus_periood_lopp",
            "element_kood": f"in.({codes})",
        },
    )
    return parse_stations(rows)


def _months(start: date, end: date):
    """(year, month, first day, last day) pieces covering start..end."""
    current = start
    while current <= end:
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        last = min(end, next_month - timedelta(days=1))
        yield current.year, current.month, current.day, last.day
        current = next_month


def fetch_rows(client: httpx.Client, table: str, element: str, start: date, end: date, station: str | None = None) -> list[dict]:
    hourly = table == "f_kliima_tund"
    rows: list[dict] = []
    for year, month, first, last in _months(start, end):
        params = {
            "select": "jaam_kood,aasta,kuu,paev" + (",tund" if hourly else "") + ",vaartus",
            "element_kood": f"eq.{element}",
            "aasta": f"eq.{year}",
            "kuu": f"eq.{month}",
            "and": f"(paev.gte.{first},paev.lte.{last})",
            "order": "jaam_kood,paev" + (",tund" if hourly else ""),
        }
        if station:
            params["jaam_kood"] = f"eq.{station}"
        rows += _get_all(client, table, params)
    return rows


def _stamp(r: dict) -> datetime:
    return datetime(r["aasta"], r["kuu"], r["paev"], r.get("tund", 0))


def daily_values(rows: list[dict], start: date, end: date) -> dict[str, dict[date, Normalized]]:
    result: dict[str, dict[date, Normalized]] = defaultdict(dict)
    for r in rows:
        day = date(r["aasta"], r["kuu"], r["paev"])
        if not start <= day <= end:
            continue
        if r.get("vaartus") is None:
            result[r["jaam_kood"]][day] = Normalized(None, False, "null")
        else:
            value = float(r["vaartus"])
            result[r["jaam_kood"]][day] = Normalized(value, True, f"{r['vaartus']}|daily")
    return result


def rain_from_hours(rows: list[dict], start: date, end: date) -> dict[str, dict[date, Normalized]]:
    """Sum hourly PR1H into our days: the hours ending 07 UTC on D to 06 UTC on D+1."""
    hours: dict[tuple[str, date], dict[datetime, float]] = defaultdict(dict)
    for r in rows:
        if r.get("vaartus") is None:
            continue
        ends = _stamp(r)
        day = (ends - timedelta(hours=7)).date()  # the hour ending 07 UTC is the first of D
        if start <= day <= end:
            hours[(r["jaam_kood"], day)][ends] = float(r["vaartus"])
    result: dict[str, dict[date, Normalized]] = defaultdict(dict)
    for (station_id, day), by_hour in hours.items():
        values = list(by_hour.values())
        if len(values) >= MIN_RAIN_HOURS:
            total = round(sum(values), 2)
            result[station_id][day] = Normalized(total, total >= 0, f"{total}|hourly{min(len(values), 24)}")
        else:
            result[station_id][day] = Normalized(None, False, f"hourly{len(values)}")
    return result


def mean_from_hours(rows: list[dict], start: date, end: date) -> dict[str, dict[date, Normalized]]:
    """Mean of the on-the-hour TA readings at 00–23 UTC on D."""
    hours: dict[tuple[str, date], dict[int, float]] = defaultdict(dict)
    for r in rows:
        if r.get("vaartus") is None:
            continue
        stamp = _stamp(r)
        if start <= stamp.date() <= end:
            hours[(r["jaam_kood"], stamp.date())][stamp.hour] = float(r["vaartus"])
    result: dict[str, dict[date, Normalized]] = defaultdict(dict)
    for (station_id, day), by_hour in hours.items():
        values = list(by_hour.values())
        if len(values) >= TEMP_MEAN_MIN_HOURS:
            mean = round(sum(values) / len(values), 1)
            result[station_id][day] = Normalized(mean, True, f"{mean}|hourly{len(values)}")
        else:
            result[station_id][day] = Normalized(None, False, f"hourly{len(values)}")
    return result


def _observes(station: _Station, element: str, start: date, end: date) -> bool:
    return any(begin <= end and (until is None or until >= start) for begin, until in station.elements.get(element, []))


def fetch_daily(
    client: httpx.Client,
    start: date,
    end: date,
    stations: list[_Station] | None = None,
    parameter: str = "precipitation",
) -> list[StationSeries]:
    stations = stations if stations is not None else fetch_stations(client)
    table, element = ELEMENTS[parameter]
    if parameter == "precipitation":
        # Our day D ends at 06 UTC on D+1.
        by_station = rain_from_hours(fetch_rows(client, table, element, start, end + timedelta(days=1)), start, end)
    elif parameter == "temp_mean":
        by_station = mean_from_hours(fetch_rows(client, table, element, start, end), start, end)
    else:
        by_station = daily_values(fetch_rows(client, table, element, start, end), start, end)

    result = []
    for s in stations:
        if not _observes(s, element, start, end):
            continue
        values = by_station.get(s.id, {})
        if parameter == "snow_depth":
            series_values = sorted((d, v) for d, v in values.items() if v.has_data)  # reported days only
        else:
            # Every day in range, so a late or missing day shows as a hollow circle.
            series_values = []
            day = start
            while day <= end:
                series_values.append((day, values.get(day, Normalized(None, False, "missing"))))
                day += timedelta(days=1)
        if not any(v.has_data for _, v in series_values) and parameter != "precipitation":
            continue
        result.append(
            StationSeries(
                source=SOURCE,
                source_station_id=s.id,
                name=s.name,
                region=None,
                lat=s.lat,
                lon=s.lon,
                country="EE",
                values=series_values,
                owner=OWNER,
                parameter=parameter,
                elevation_m=s.elevation_m,
            )
        )
    return result


def fetch_hourly_precipitation(client: httpx.Client, station_id: str, day: date) -> list[float]:
    """Hourly rainfall for our day D at one station, to confirm unusually high values."""
    rows = fetch_rows(client, "f_kliima_tund", "PR1H", day, day + timedelta(days=1), station=station_id)
    first, last = datetime.combine(day, datetime.min.time()) + timedelta(hours=7), datetime.combine(day, datetime.min.time()) + timedelta(hours=30)
    return [float(r["vaartus"]) for r in rows if r.get("vaartus") is not None and first <= _stamp(r) <= last]

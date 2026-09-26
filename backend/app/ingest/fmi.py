"""Client and parser for FMI open data daily precipitation (rrday).

Facts verified against the live API (2026-09):
- A value labelled date D covers 06 UTC on D to 06 UTC on D+1, so yesterday's
  value exists only after 06 UTC today. We store FMI's label date as-is.
- "-1.0" means no precipitation, "0.0" means a trace (< 0.05 mm), "NaN" means missing.
- Snow depth ("snow", cm) is a morning reading on the label date; "-1.0" means no snow
  cover. Both parameters come from the same request, one member per station and parameter.
- Temperature: daily `tmin`/`tmax` cover 18 UTC on D-1 to 18 UTC on D, labelled D (checked
  against hourly min/max, 63/63 days), so they're used as they are. Daily `tday` is the
  Finnish local calendar day, not 00–24 UTC, so the mean is computed from the hourly
  averages `TA_PT1H_AVG` (hours ending after 00 UTC up to 24 UTC; at least 20 of 24).
  -1.0 is a real temperature: the "none" codes apply to rain and snow only.
- The timevaluepair format carries fmisid, name and region per station; the
  simple format has coordinates only.
"""

import logging
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

import httpx

from app.ingest.common import Normalized, StationSeries

logger = logging.getLogger(__name__)

WFS_URL = "https://opendata.fmi.fi/wfs"
STORED_QUERY = "fmi::observations::weather::daily::timevaluepair"
# Covers all of Finland including Åland and Lapland (lon,lat,lon,lat).
FINLAND_BBOX = "19,59,32,71"
SOURCE = "fmi"
# FMI parameter name -> our measurement type.
PARAMETERS = {"rrday": "precipitation", "snow": "snow_depth", "tmin": "temp_min", "tmax": "temp_max"}
TEMPERATURE_PARAMETERS = {"tmin", "tmax"}
HOURLY_MEAN_MIN_HOURS = 20
HOURLY_CHUNK_DAYS = 7

NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "target": "http://xml.fmi.fi/namespace/om/atmosphericfeatures/1.1",
    "wml2": "http://www.opengis.net/waterml/2.0",
}
FMISID_CODESPACE = "http://xml.fmi.fi/namespace/stationcode/fmisid"
NAME_CODESPACE = "http://xml.fmi.fi/namespace/locationcode/name"


def normalize(raw: str, temperature: bool = False) -> Normalized:
    raw = raw.strip()
    try:
        value = float(raw)
    except ValueError:
        return Normalized(None, False, raw)
    if value != value:  # NaN
        return Normalized(None, False, raw)
    if temperature:
        return Normalized(value, True, raw)
    if value == -1.0:
        return Normalized(0.0, True, raw)
    if value < 0:
        return Normalized(None, False, raw)
    return Normalized(value, True, raw)


def parse_timevaluepair(xml: bytes | str) -> list[StationSeries]:
    root = ET.fromstring(xml)
    stations: list[StationSeries] = []
    for member in root.findall("wfs:member", NS):
        location = member.find(".//target:Location", NS)
        pos = member.find(".//gml:Point/gml:pos", NS)
        if location is None or pos is None:
            continue

        fmisid = next(
            (el.text for el in location.findall("gml:identifier", NS) if el.get("codeSpace") == FMISID_CODESPACE),
            None,
        )
        name = next(
            (el.text for el in location.findall("gml:name", NS) if el.get("codeSpace") == NAME_CODESPACE),
            None,
        )
        if not fmisid or not name:
            continue
        region = location.findtext("target:region", default=None, namespaces=NS)
        observed = member.find(".//{http://www.opengis.net/om/2.0}observedProperty")
        href = observed.get("{http://www.w3.org/1999/xlink}href", "") if observed is not None else ""
        fmi_param = next((p for p in PARAMETERS if f"param={p}&" in href or href.endswith(f"param={p}")), "rrday")
        lat, lon = (float(x) for x in pos.text.split()[:2])

        series = StationSeries(
            source=SOURCE,
            source_station_id=fmisid.strip(),
            name=name.strip(),
            region=region.strip() if region else None,
            lat=lat,
            lon=lon,
            country="FI",
            parameter=PARAMETERS[fmi_param],
        )
        for tvp in member.iterfind(".//wml2:MeasurementTVP", NS):
            time_text = tvp.findtext("wml2:time", namespaces=NS)
            value_text = tvp.findtext("wml2:value", namespaces=NS)
            if time_text and value_text is not None:
                # FMI's label date already matches our convention (06 UTC on D to 06 UTC on D+1).
                series.values.append(
                    (date.fromisoformat(time_text.strip()[:10]), normalize(value_text, fmi_param in TEMPERATURE_PARAMETERS))
                )
        stations.append(series)
    return stations


def fetch_daily(client: httpx.Client, start: date, end: date, retries: int = 3) -> list[StationSeries]:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "getFeature",
        "storedquery_id": STORED_QUERY,
        "bbox": FINLAND_BBOX,
        "parameters": ",".join(PARAMETERS),
        "starttime": f"{start.isoformat()}T00:00:00Z",
        "endtime": f"{end.isoformat()}T00:00:00Z",
    }
    series = parse_timevaluepair(_get_wfs(client, params, retries))
    # Rain-only stations list tmin/tmax as NaN: no temperature rows for them.
    temperatures = {PARAMETERS[p] for p in TEMPERATURE_PARAMETERS}
    return [s for s in series if s.parameter not in temperatures or any(v.has_data for _, v in s.values)]


def _get_wfs(client: httpx.Client, params: dict, retries: int = 3) -> bytes:
    for attempt in range(1, retries + 1):
        try:
            response = client.get(WFS_URL, params=params)
            response.raise_for_status()
            ET.fromstring(response.content)  # a truncated answer is retried too
            return response.content
        except (httpx.HTTPError, ET.ParseError) as exc:
            if attempt == retries:
                raise
            wait = 5 * attempt
            logger.warning("FMI request %s..%s failed (%s), retrying in %ss", params["starttime"], params["endtime"], exc, wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")


HOURLY_QUERY = "fmi::observations::weather::hourly::timevaluepair"


def fetch_hourly_precipitation(client: httpx.Client, fmisid: str, day: date) -> list[float]:
    """Hourly rainfall (PRA_PT1H_ACC, mm) for our day D: the hours ending 07 UTC on D through
    06 UTC on D+1. Missing hours are left out. Used to confirm unusually high daily values."""
    response = client.get(
        WFS_URL,
        params={
            "service": "WFS",
            "version": "2.0.0",
            "request": "getFeature",
            "storedquery_id": HOURLY_QUERY,
            "fmisid": fmisid,
            "parameters": "PRA_PT1H_ACC",
            "starttime": f"{day.isoformat()}T07:00:00Z",
            "endtime": f"{(day + timedelta(days=1)).isoformat()}T06:00:00Z",
        },
    )
    response.raise_for_status()
    values = []
    for tvp in ET.fromstring(response.content).iterfind(".//wml2:MeasurementTVP", NS):
        text = (tvp.findtext("wml2:value", namespaces=NS) or "").strip()
        try:
            value = float(text)
        except ValueError:
            continue
        if value == value and value >= 0:  # skip NaN and negative codes
            values.append(value)
    return values


def parse_hourly_mean(xml: bytes | str, start: date, end: date) -> list[StationSeries]:
    """Hourly TA_PT1H_AVG -> daily 00–24 UTC means (`temp_mean`). A time marks the end of its
    hour, so day D takes the hours ending after 00:00 up to 24:00 UTC."""
    root = ET.fromstring(xml)
    result: list[StationSeries] = []
    for member in root.findall("wfs:member", NS):
        location = member.find(".//target:Location", NS)
        pos = member.find(".//gml:Point/gml:pos", NS)
        if location is None or pos is None:
            continue
        fmisid = next(
            (el.text for el in location.findall("gml:identifier", NS) if el.get("codeSpace") == FMISID_CODESPACE), None
        )
        name = next((el.text for el in location.findall("gml:name", NS) if el.get("codeSpace") == NAME_CODESPACE), None)
        if not fmisid or not name:
            continue
        by_day: dict[date, list[float]] = {}
        for tvp in member.iterfind(".//wml2:MeasurementTVP", NS):
            time_text = tvp.findtext("wml2:time", namespaces=NS)
            try:
                value = float((tvp.findtext("wml2:value", namespaces=NS) or "").strip())
            except ValueError:
                continue
            if not time_text or value != value:
                continue
            ends = datetime.fromisoformat(time_text.strip().replace("Z", "+00:00"))
            day = (ends - timedelta(minutes=1)).date()  # the hour ending 00:00 belongs to the day before
            if start <= day <= end:
                by_day.setdefault(day, []).append(value)
        lat, lon = (float(x) for x in pos.text.split()[:2])
        region = location.findtext("target:region", default=None, namespaces=NS)
        series = StationSeries(
            source=SOURCE,
            source_station_id=fmisid.strip(),
            name=name.strip(),
            region=region.strip() if region else None,
            lat=lat,
            lon=lon,
            country="FI",
            parameter="temp_mean",
        )
        for day in sorted(by_day):
            hours = by_day[day]
            if len(hours) >= HOURLY_MEAN_MIN_HOURS:
                mean = round(sum(hours) / len(hours), 1)
                series.values.append((day, Normalized(mean, True, f"{mean}|hourly{len(hours)}")))
            else:
                series.values.append((day, Normalized(None, False, f"hourly{len(hours)}")))
        if series.values:
            result.append(series)
    return result


def fetch_daily_mean_temperature(client: httpx.Client, start: date, end: date) -> list[StationSeries]:
    """Daily 00–24 UTC mean temperature for all Finnish stations, from hourly averages."""
    merged: dict[str, StationSeries] = {}
    day = start
    while day <= end:
        chunk_end = min(day + timedelta(days=HOURLY_CHUNK_DAYS - 1), end)
        content = _get_wfs(
            client,
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "getFeature",
                "storedquery_id": HOURLY_QUERY,
                "bbox": FINLAND_BBOX,
                "parameters": "TA_PT1H_AVG",
                "starttime": f"{day.isoformat()}T01:00:00Z",
                "endtime": f"{(chunk_end + timedelta(days=1)).isoformat()}T00:00:00Z",
            },
        )
        for series in parse_hourly_mean(content, day, chunk_end):
            if series.source_station_id in merged:
                merged[series.source_station_id].values += series.values
            else:
                merged[series.source_station_id] = series
        day = chunk_end + timedelta(days=1)
    return list(merged.values())

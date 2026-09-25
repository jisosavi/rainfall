"""Client and parser for FMI open data daily precipitation (rrday).

Facts verified against the live API (2026-09):
- A value labelled date D covers 06 UTC on D to 06 UTC on D+1, so yesterday's
  value exists only after 06 UTC today. We store FMI's label date as-is.
- "-1.0" means no precipitation, "0.0" means a trace (< 0.05 mm), "NaN" means missing.
- The timevaluepair format carries fmisid, name and region per station; the
  simple format has coordinates only.
"""

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, timedelta

import httpx

logger = logging.getLogger(__name__)

WFS_URL = "https://opendata.fmi.fi/wfs"
STORED_QUERY = "fmi::observations::weather::daily::timevaluepair"
# Covers all of Finland including Åland and Lapland (lon,lat,lon,lat).
FINLAND_BBOX = "19,59,32,71"
CHUNK_DAYS = 31

NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "target": "http://xml.fmi.fi/namespace/om/atmosphericfeatures/1.1",
    "wml2": "http://www.opengis.net/waterml/2.0",
}
FMISID_CODESPACE = "http://xml.fmi.fi/namespace/stationcode/fmisid"
NAME_CODESPACE = "http://xml.fmi.fi/namespace/locationcode/name"


@dataclass
class StationSeries:
    fmisid: str
    name: str
    region: str | None
    lat: float
    lon: float
    values: list[tuple[date, str]] = field(default_factory=list)  # (label date, raw value text)


@dataclass(frozen=True)
class Normalized:
    precipitation_mm: float | None
    has_data: bool
    raw_status: str


def normalize(raw: str) -> Normalized:
    raw = raw.strip()
    try:
        value = float(raw)
    except ValueError:
        return Normalized(None, False, raw)
    if value != value:  # NaN
        return Normalized(None, False, raw)
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
        lat, lon = (float(x) for x in pos.text.split()[:2])

        series = StationSeries(fmisid=fmisid.strip(), name=name.strip(), region=region.strip() if region else None, lat=lat, lon=lon)
        for tvp in member.iterfind(".//wml2:MeasurementTVP", NS):
            time_text = tvp.findtext("wml2:time", namespaces=NS)
            value_text = tvp.findtext("wml2:value", namespaces=NS)
            if time_text and value_text is not None:
                series.values.append((date.fromisoformat(time_text.strip()[:10]), value_text))
        stations.append(series)
    return stations


def date_chunks(start: date, end: date, days: int = CHUNK_DAYS):
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=days - 1), end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def fetch_daily(client: httpx.Client, start: date, end: date, retries: int = 3) -> list[StationSeries]:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "getFeature",
        "storedquery_id": STORED_QUERY,
        "bbox": FINLAND_BBOX,
        "parameters": "rrday",
        "starttime": f"{start.isoformat()}T00:00:00Z",
        "endtime": f"{end.isoformat()}T00:00:00Z",
    }
    for attempt in range(1, retries + 1):
        try:
            response = client.get(WFS_URL, params=params)
            response.raise_for_status()
            return parse_timevaluepair(response.content)
        except (httpx.HTTPError, ET.ParseError) as exc:
            if attempt == retries:
                raise
            wait = 5 * attempt
            logger.warning("FMI request %s..%s failed (%s), retrying in %ss", start, end, exc, wait)
            time.sleep(wait)
    return []

import copy
import json
from datetime import date
from pathlib import Path

import httpx
from sqlalchemy import select

from app.db.models import DailyValue, Station
from app.ingest import met
from app.ingest.service import store_series

# Real Frost responses (2026-09-15..19 labels) for Oslo Blindern, Svalbard Lufthavn and a
# Swedish station, trimmed to the fields we use.
REAL = json.loads((Path(__file__).parent / "fixtures" / "frost_daily.json").read_text())


def fixture():
    data = copy.deepcopy(REAL)
    # The Swedish station has no PT6H series in reality; add one to prove the country filter.
    data["availableTimeSeries"]["data"].append(
        {"sourceId": "SN201300:0", "validFrom": "2000-01-01T00:00:00.000Z", "timeOffset": "PT6H", "timeSeriesId": 0}
    )
    obs = data["observations"]["data"]
    # Drop Oslo's 2026-09-17 value to test missing-day filling.
    obs[:] = [o for o in obs if not (o["sourceId"] == "SN18700:0" and o["referenceTime"].startswith("2026-09-17"))]
    # Mark Svalbard's 2026-09-15 value as erroneous (quality code 6).
    next(o for o in obs if o["sourceId"] == "SN99840:0" and o["referenceTime"].startswith("2026-09-15"))[
        "observations"
    ][0]["qualityCode"] = 6
    return data


def mock_client(data):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path.startswith("/observations/availableTimeSeries"):
            return httpx.Response(200, json=data["availableTimeSeries"])
        if path.startswith("/sources"):
            return httpx.Response(200, json=data["sources"])
        if path.startswith("/observations"):
            return httpx.Response(200, json=data["observations"])
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler), base_url=met.FROST_URL), requests


def fetch(start=date(2026, 9, 14), end=date(2026, 9, 18)):
    client, requests = mock_client(fixture())
    with client:
        return met.fetch_daily(client, start, end), requests


def test_stations_filtered_to_norway_and_svalbard_with_tidy_names():
    series, _ = fetch()
    by_id = {s.source_station_id: s for s in series}
    assert set(by_id) == {"SN18700", "SN99840"}  # Swedish station dropped
    oslo, svalbard = by_id["SN18700"], by_id["SN99840"]
    assert (oslo.name, oslo.region, oslo.country, oslo.source) == ("Oslo - Blindern", "Oslo", "NO", "met")
    assert (svalbard.name, svalbard.country) == ("Svalbard Lufthavn", "SJ")
    assert oslo.lat > 59 and oslo.lon > 10


def test_dates_shifted_to_fmi_convention():
    series, requests = fetch()
    oslo = {d: v for d, v in next(s for s in series if s.source_station_id == "SN18700").values}
    # Frost label 2026-09-16 (15 Sept 06 UTC → 16 Sept 06 UTC) is stored under 2026-09-15.
    assert oslo[date(2026, 9, 15)].value == 14.9
    assert oslo[date(2026, 9, 14)].value == 1.2
    # Stored dates 14..18 need Frost labels 15..19, and Frost's end date is exclusive.
    obs_request = next(r for r in requests if r.url.path == "/observations/v0.jsonld")
    assert obs_request.url.params["referencetime"] == "2026-09-15/2026-09-20"
    assert obs_request.url.params["timeoffsets"] == "PT6H"


def test_missing_days_and_bad_quality_become_hollow():
    series, _ = fetch()
    oslo = {d: v for d, v in next(s for s in series if s.source_station_id == "SN18700").values}
    svalbard = {d: v for d, v in next(s for s in series if s.source_station_id == "SN99840").values}
    assert sorted(oslo) == [date(2026, 9, d) for d in range(14, 19)]  # every day present
    assert (oslo[date(2026, 9, 16)].has_data, oslo[date(2026, 9, 16)].raw_status) == (False, "missing")
    assert (svalbard[date(2026, 9, 14)].has_data, svalbard[date(2026, 9, 14)].raw_status) == (False, "0.4|q6")
    assert (svalbard[date(2026, 9, 15)].value, svalbard[date(2026, 9, 15)].has_data) == (0.0, True)


def test_frost_404_means_no_data():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)), base_url=met.FROST_URL)
    with client:
        assert met.fetch_daily(client, date(2026, 9, 14), date(2026, 9, 18)) == []


def test_fmi_and_met_stations_coexist(db):
    from app.ingest.fmi import parse_timevaluepair

    fmi_fixture = (Path(__file__).parent / "fixtures" / "fmi_daily_timevaluepair.xml").read_bytes()
    met_series, _ = fetch()
    store_series(db, parse_timevaluepair(fmi_fixture))
    store_series(db, met_series)
    store_series(db, met_series)  # idempotent

    sources = db.execute(select(Station.source, Station.country)).all()
    assert sorted(set(sources)) == [("fmi", "FI"), ("met", "NO"), ("met", "SJ")]
    assert db.scalar(select(DailyValue.value).join(Station).where(
        Station.source_station_id == "SN18700", DailyValue.date == date(2026, 9, 15)
    )) == 14.9


SNOW = json.loads((Path(__file__).parent / "fixtures" / "frost_snow.json").read_text())


def test_snow_depth_no_date_shift_and_only_reported_days():
    # Real Frost responses, labels 2026-02-10..13: Oslo Blindern and a snow-only road station.
    client, requests = mock_client(copy.deepcopy(SNOW))
    with client:
        series = met.fetch_daily(client, date(2026, 2, 10), date(2026, 2, 16), parameter="snow_depth")
    by_id = {s.source_station_id: s for s in series}
    assert set(by_id) == {"SN18700", "SN89233"}
    oslo = by_id["SN18700"]
    assert oslo.parameter == "snow_depth"
    # A reading at 06 UTC on the label date: stored under the same date, no shift.
    assert [(d, v.value) for d, v in oslo.values] == [
        (date(2026, 2, 10), 10.0), (date(2026, 2, 11), 10.0), (date(2026, 2, 12), 10.0), (date(2026, 2, 13), 11.0)
    ]
    # Days 14-16 were not reported: no missing rows for snow.
    assert max(d for d, _ in oslo.values) == date(2026, 2, 13)
    obs_request = next(r for r in requests if r.url.path == "/observations/v0.jsonld")
    assert obs_request.url.params["referencetime"] == "2026-02-10/2026-02-17"
    assert obs_request.url.params["elements"] == "surface_snow_thickness"
    assert obs_request.url.params["timeresolutions"] == "P1D"


def test_tidy_owner():
    # Real Frost station holders.
    assert met.tidy_owner(["STATENS VEGVESEN"]) == "Statens vegvesen"
    assert met.tidy_owner(["MET.NO"]) == "MET Norway"
    assert met.tidy_owner(["AVINOR", "MET.NO"]) == "Avinor, MET Norway"
    assert met.tidy_owner(["BANE NOR"]) == "Bane NOR"
    assert met.tidy_owner(["NVE SEKSJON FOR FJELLSKRED"]) == "NVE seksjon for fjellskred"
    assert met.tidy_owner(["TRONDHEIM KOMMUNE"]) == "Trondheim kommune"
    assert met.tidy_owner(["ukjent - sjekk tabellen person i stedet for organisation", "Private owner"]) == "Private owner"
    assert met.tidy_owner([]) is None

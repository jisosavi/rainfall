import copy
import json
from datetime import date
from pathlib import Path

import httpx

from app.ingest import dmi

# Real DMI climateData responses: Rødbyhavn (DK), Havn/Tórshavn (FO), Aasiaat (GL) and
# Flyvestation Skrydstrup (DK, snow depth); hourly and daily rainfall 10-12 Sept 2026,
# snow depth 9-12 Feb 2026.
REAL = json.loads((Path(__file__).parent / "fixtures" / "dmi.json").read_text())


def mock_client(data):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        params = request.url.params
        if request.url.path.endswith("/station/items"):
            return httpx.Response(200, json=data["stations"])
        if params.get("parameterId") == "snow_depth":
            return httpx.Response(200, json=data["snow"])
        if params.get("timeResolution") == "hour":
            return httpx.Response(200, json=data["hourly"])
        return httpx.Response(200, json=data["daily"])

    return httpx.Client(transport=httpx.MockTransport(handler)), requests


def test_stations_countries_owner_elevation():
    stations = {s.id: s for s in dmi.parse_stations(REAL["stations"]["features"], date(2026, 9, 10), date(2026, 9, 11))}
    assert (stations["05970"].name, stations["05970"].country, stations["05970"].owner) == ("Rødbyhavn", "DK", "DMI")
    assert (stations["06011"].country, stations["06011"].owner, stations["06011"].elevation_m) == ("FO", "Havne Kommuner mv", 54.0)
    assert stations["04220"].country == "GL"
    assert stations["06110"].owner == "Forsvaret"


def test_rainfall_is_summed_from_hours_06_to_06_utc():
    client, requests = mock_client(copy.deepcopy(REAL))
    with client:
        series = dmi.fetch_daily(client, date(2026, 9, 10), date(2026, 9, 11))
    by_id = {s.source_station_id: dict(s.values) for s in series}
    # Hourly sums 06-06 UTC. For Havn, DMI's own daily values (5.6, 1.6 mm) are really
    # 00-24 UTC days despite their 06 UTC labels, so they must not be used.
    assert (by_id["06011"][date(2026, 9, 10)].value, by_id["06011"][date(2026, 9, 11)].value) == (6.0, 3.0)
    assert by_id["05970"][date(2026, 9, 11)].value == 0.2
    assert by_id["04220"][date(2026, 9, 10)].raw_status == "0.1|hourly24"
    hourly_request = next(r for r in requests if r.url.params.get("timeResolution") == "hour")
    assert hourly_request.url.params["datetime"] == "2026-09-10T06:00:00Z/2026-09-12T06:00:00Z"


def test_one_missing_hour_counts_two_do_not():
    data = copy.deepcopy(REAL)
    hours = data["hourly"]["features"]

    def drop(day_hour):
        victim = next(f for f in hours if f["properties"]["stationId"] == "06011" and f["properties"]["from"].startswith(day_hour))
        hours.remove(victim)

    drop("2026-09-10T12")  # our 10 Sept: 23 hours
    drop("2026-09-11T12")  # our 11 Sept: 22 hours
    drop("2026-09-11T13")
    client, _ = mock_client(data)
    with client:
        series = dmi.fetch_daily(client, date(2026, 9, 10), date(2026, 9, 11))
    havn = dict(next(s for s in series if s.source_station_id == "06011").values)
    assert havn[date(2026, 9, 10)].has_data and havn[date(2026, 9, 10)].raw_status.endswith("|hourly23")
    assert (havn[date(2026, 9, 11)].has_data, havn[date(2026, 9, 11)].raw_status) == (False, "hourly22")


def test_station_without_hourly_data_gets_no_rows():
    data = copy.deepcopy(REAL)
    data["hourly"]["features"] = [f for f in data["hourly"]["features"] if f["properties"]["stationId"] != "04220"]
    client, _ = mock_client(data)
    with client:
        series = dmi.fetch_daily(client, date(2026, 9, 10), date(2026, 9, 11))
    assert "04220" not in {s.source_station_id for s in series}


def test_snow_depth_daily_06_utc_reported_days_only():
    client, _ = mock_client(copy.deepcopy(REAL))
    with client:
        series = dmi.fetch_daily(client, date(2026, 2, 9), date(2026, 2, 12), parameter="snow_depth")
    assert [s.source_station_id for s in series] == ["06110"]
    values = dict(series[0].values)
    assert sorted(values) == [date(2026, 2, 9), date(2026, 2, 10), date(2026, 2, 12)]  # 11 Feb not reported
    assert values[date(2026, 2, 10)].value == 2.0 and series[0].parameter == "snow_depth"

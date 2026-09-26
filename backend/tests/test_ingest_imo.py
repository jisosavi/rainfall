import copy
import json
from datetime import date
from pathlib import Path

import httpx

from app.ingest import imo

# Real IMO responses: stations Reykjavík (1, staffed), Neðra-Skarð (97, manual rain),
# Mjólkárvirkjun (231) and Auðnir (420); EDR r09 for labels 10-14 Jan 2026; synop 1-4 Feb 2026.
REAL = json.loads((Path(__file__).parent / "fixtures" / "imo.json").read_text())


def mock_client(data):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path.endswith("/stations"):
            return httpx.Response(200, json=data["stations"])
        if path.endswith("/rodeo/collections/day/cube"):
            return httpx.Response(200, json=data["r09_cube"])
        if path.endswith("/observations/synop"):
            return httpx.Response(200, json=data["synop"])
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler)), requests


def test_stations_and_owner_tidied():
    stations = {s.id: s for s in imo.parse_stations(REAL["stations"])}
    assert (stations["1"].name, stations["1"].type, stations["1"].elevation_m) == ("Reykjavík", "sk", 60.2000007629)
    assert imo._tidy_owner(", Veðurstofa Íslands - Ofanflóð") == "Veðurstofa Íslands - Ofanflóð"


def test_r09_label_is_stored_one_day_earlier():
    client, requests = mock_client(copy.deepcopy(REAL))
    with client:
        series = imo.fetch_daily(client, date(2026, 1, 9), date(2026, 1, 13))
    by_id = {s.source_station_id: dict(s.values) for s in series}
    # Label 13 Jan (09 UTC 12 Jan -> 09 UTC 13 Jan) is stored under 12 Jan.
    assert by_id["97"] == {date(2026, 1, 12): imo.Normalized(0.4, True, "0.4|r09")}
    assert by_id["1"][date(2026, 1, 12)].value == 0.0
    assert all(s.country == "IS" and s.source == "imo" for s in series)
    cube = next(r for r in requests if r.url.path.endswith("/cube"))
    assert cube.url.params["datetime"] == "2026-01-10T00:00:00Z/2026-01-14T00:00:00Z"
    assert cube.url.params["parameter-name"] == "r09"


def test_snow_depth_from_09_utc_readings():
    client, _ = mock_client(copy.deepcopy(REAL))
    with client:
        series = imo.fetch_daily(client, date(2026, 2, 1), date(2026, 2, 4), parameter="snow_depth")
    by_id = {s.source_station_id: dict(s.values) for s in series}
    assert [v.value for _, v in sorted(by_id["420"].items())] == [2.0, 2.0, 1.0, 1.0]  # snd, cm
    # Mjólkárvirkjun: partly covered without a depth is unknown; "No snow" on 4 Feb is 0 cm.
    assert by_id["231"] == {date(2026, 2, 4): imo.Normalized(0.0, True, "0|sncm0")}


def test_no_data_404_is_empty():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    with client:
        assert imo.fetch_daily(client, date(2026, 1, 9), date(2026, 1, 13), stations=[]) == []

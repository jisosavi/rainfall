import json
from datetime import date
from pathlib import Path

import httpx
from sqlalchemy import select

from app.db.models import DailyValue, Station
from app.ingest import smhi
from app.ingest.service import run_ingest

FIXTURES = Path(__file__).parent / "fixtures"
# Real SMHI responses: parameter 5 station list (Stockholm, a VA Syd station, Aapua closed
# in 1968), Stockholm's latest-months (refs 2026-09-15..24) and its archive CSV (trimmed).
PARAMETER = json.loads((FIXTURES / "smhi_parameter5.json").read_text())
LATEST = json.loads((FIXTURES / "smhi_latest_months_98230.json").read_text())
ARCHIVE = (FIXTURES / "smhi_archive_98230.csv").read_text(encoding="utf-8")
STOCKHOLM, VA_SYD = "98230", "22126231"


def mock_client():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        path = request.url.path
        if path.endswith("/parameter/5.json"):
            return httpx.Response(200, json=PARAMETER)
        if path.endswith(f"/station/{STOCKHOLM}/period/latest-months/data.json"):
            return httpx.Response(200, json=LATEST)
        if path.endswith(f"/station/{STOCKHOLM}/period/corrected-archive/data.csv"):
            return httpx.Response(200, text=ARCHIVE)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler)), requests


def test_station_list_keeps_overlapping_stations_with_owner():
    stations = smhi.parse_stations(PARAMETER, date(2025, 1, 1), date(2026, 9, 24))
    by_id = {s.id: s for s in stations}
    assert set(by_id) == {STOCKHOLM, VA_SYD}  # Aapua closed in 1968
    assert by_id[STOCKHOLM].name == "Stockholm-Observatoriekullen A"  # SMHI naming kept
    assert by_id[STOCKHOLM].owner == "SMHI"
    assert by_id[VA_SYD].owner == "VA Syd"


def test_latest_months_ref_is_stored_as_is():
    values = smhi.parse_latest_months(LATEST)
    assert min(values) == date(2026, 9, 15) and max(values) == date(2026, 9, 24)
    assert all(v.raw_status.endswith("|G") for v in values.values())


def test_archive_csv_skips_metadata_and_filters_by_start():
    values = smhi.parse_archive_csv(ARCHIVE, date(2026, 5, 25))
    assert min(values) == date(2026, 5, 25) and max(values) == date(2026, 5, 31)
    assert smhi.parse_archive_csv(ARCHIVE, date(1990, 1, 1))[date(1996, 10, 2)].value == 0.6


def test_normalize_quality():
    assert smhi.normalize("4.2", "G") == smhi.Normalized(4.2, True, "4.2|G")
    assert smhi.normalize("4.2", "Y").has_data is True  # newest, not yet checked
    assert smhi.normalize("4.2", "R").has_data is False
    assert smhi.normalize(None, None).has_data is False


def test_recent_range_uses_latest_months_only_and_fills_missing():
    client, requests = mock_client()
    with client:
        series = smhi.fetch_daily(client, date(2026, 9, 20), date(2026, 9, 24), today=date(2026, 9, 25))
    assert not any("corrected-archive" in r for r in requests)
    by_id = {s.source_station_id: s for s in series}
    stockholm = dict(by_id[STOCKHOLM].values)
    assert sorted(stockholm) == [date(2026, 9, d) for d in range(20, 25)]
    assert all(v.has_data for v in stockholm.values())
    assert (by_id[STOCKHOLM].country, by_id[STOCKHOLM].source) == ("SE", "smhi")
    # The VA Syd station has no data in the mock: every day becomes a missing row.
    assert {v.raw_status for _, v in by_id[VA_SYD].values} == {"missing"}


def test_old_range_uses_archive():
    client, requests = mock_client()
    with client:
        series = smhi.fetch_daily(client, date(2026, 5, 25), date(2026, 9, 24), today=date(2026, 9, 25))
    assert any("corrected-archive" in r for r in requests)
    stockholm = dict(next(s for s in series if s.source_station_id == STOCKHOLM).values)
    assert stockholm[date(2026, 5, 31)].has_data  # from the archive
    assert stockholm[date(2026, 9, 24)].has_data  # from latest-months
    assert stockholm[date(2026, 7, 1)].raw_status == "missing"  # gap in the trimmed fixtures


def test_store_in_chunks_with_owner(db):
    client, _ = mock_client()
    with client:
        series = smhi.fetch_daily(client, date(2026, 8, 1), date(2026, 9, 24), today=date(2026, 9, 25))
    total = run_ingest(db, lambda a, b: smhi.slice_series(series, a, b), date(2026, 8, 1), date(2026, 9, 24))
    assert total == 2 * 55
    owners = dict(db.execute(select(Station.source_station_id, Station.owner).where(Station.source == "smhi")).all())
    assert owners == {STOCKHOLM: "SMHI", VA_SYD: "VA Syd"}
    assert db.scalar(
        select(DailyValue.has_data).join(Station).where(
            Station.source_station_id == STOCKHOLM, DailyValue.date == date(2026, 9, 24)
        )
    )


PARAM8 = json.loads((FIXTURES / "smhi_parameter8.json").read_text())
SNOW_LATEST = json.loads((FIXTURES / "smhi_snow_latest_months_180960.json").read_text())
SNOW_ARCHIVE = (FIXTURES / "smhi_snow_archive_180960.csv").read_text(encoding="utf-8")


def test_snow_archive_csv_metres_to_cm():
    # Real Kiruna archive rows: "2026-02-10;06:00:00;0.58;G" is 58 cm.
    values = smhi.parse_archive_csv(SNOW_ARCHIVE, date(2026, 2, 8), scale=100)
    assert (values[date(2026, 2, 10)].value, values[date(2026, 2, 10)].raw_status) == (58.0, "0.58|G")
    assert min(values) == date(2026, 2, 8) and max(values) == date(2026, 2, 14)


def test_snow_latest_months_uses_timestamp_date():
    values = smhi.parse_latest_months(SNOW_LATEST, scale=100)
    # Timestamps are 06:00 UTC readings; their UTC date is the reading's date.
    dates = sorted(values)
    assert all(v.value == 0.0 and v.has_data for v in values.values())  # late-summer: no snow
    assert dates[-1] == date(2026, 9, 24)
    assert (dates[-1] - dates[-2]).days == 3  # a real 3-day gap: reported days only


def test_snow_fetch_only_reported_days():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/parameter/8.json"):
            return httpx.Response(200, json=PARAM8)
        if path.endswith("/parameter/8/station/180960/period/latest-months/data.json"):
            return httpx.Response(200, json=SNOW_LATEST)
        if path.endswith("/parameter/8/station/180960/period/corrected-archive/data.csv"):
            return httpx.Response(200, text=SNOW_ARCHIVE)
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        series = smhi.fetch_daily(
            client, date(2026, 2, 1), date(2026, 9, 24), today=date(2026, 9, 25), parameter="snow_depth"
        )
    assert [s.source_station_id for s in series] == ["180960"]  # Aapua closed long ago
    kiruna = series[0]
    assert kiruna.parameter == "snow_depth"
    values = dict(kiruna.values)
    assert values[date(2026, 2, 10)].value == 58.0  # from the archive
    assert date(2026, 3, 1) not in values  # not in the trimmed fixtures, and not filled in
    assert all(v.has_data for v in values.values())


def test_implausible_values_become_missing(db):
    # Real SMHI value for Söråker (Sundsvalls kommun), 2026-05-17: "17280.0" with quality Y.
    from app.ingest.common import StationSeries
    from app.ingest.service import store_series

    series = StationSeries(
        source="smhi", source_station_id="22228110", name="Söråker", region=None, lat=62.49, lon=17.51, country="SE",
        values=[(date(2026, 5, 17), smhi.normalize("17280.0", "Y")), (date(2026, 5, 18), smhi.normalize("140.0", "G"))],
    )
    store_series(db, [series])
    rows = dict(db.execute(select(DailyValue.date, DailyValue)).tuples().all())
    assert (rows[date(2026, 5, 17)].has_data, rows[date(2026, 5, 17)].value) == (False, None)
    assert rows[date(2026, 5, 17)].raw_status == "17280.0|Y|implausible"
    assert (rows[date(2026, 5, 18)].has_data, rows[date(2026, 5, 18)].value) == (True, 140.0)  # heavy but real

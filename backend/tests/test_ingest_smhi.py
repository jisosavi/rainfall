import json
from datetime import date
from pathlib import Path

import httpx
from sqlalchemy import select

from app.db.models import DailyPrecipitation, Station
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
    assert smhi.parse_archive_csv(ARCHIVE, date(1990, 1, 1))[date(1996, 10, 2)].precipitation_mm == 0.6


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
        select(DailyPrecipitation.has_data).join(Station).where(
            Station.source_station_id == STOCKHOLM, DailyPrecipitation.date == date(2026, 9, 24)
        )
    )

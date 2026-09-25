from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.db.models import DailyPrecipitation, Station
from app.ingest.fmi import date_chunks, normalize, parse_timevaluepair
from app.ingest.service import default_range, run_ingest, store_series

FIXTURE = (Path(__file__).parent / "fixtures" / "fmi_daily_timevaluepair.xml").read_bytes()


def test_parse_real_fmi_response():
    stations = parse_timevaluepair(FIXTURE)
    by_id = {s.fmisid: s for s in stations}
    assert set(by_id) == {"100908", "101049", "100963"}
    uto = by_id["100908"]
    assert uto.name == "Parainen Utö"
    assert uto.region == "Parainen"
    assert (uto.lat, uto.lon) == (59.77909, 21.37479)
    assert [d for d, _ in uto.values] == [date(2026, 9, 20), date(2026, 9, 21), date(2026, 9, 22)]
    assert [v for _, v in by_id["100963"].values] == ["0.7", "0.0", "NaN"]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("-1.0", (0.0, True)),  # FMI: no precipitation
        ("0.0", (0.0, True)),  # FMI: trace
        ("4.5", (4.5, True)),
        ("NaN", (None, False)),
        ("garbage", (None, False)),
        ("-3.0", (None, False)),
    ],
)
def test_normalize(raw, expected):
    value = normalize(raw)
    assert (value.precipitation_mm, value.has_data) == expected
    assert value.raw_status == raw


def test_store_series_is_idempotent_and_updates(db):
    series = parse_timevaluepair(FIXTURE)
    assert store_series(db, series) == 9
    assert store_series(db, series) == 9
    assert db.scalar(select(func.count()).select_from(Station)) == 3
    assert db.scalar(select(func.count()).select_from(DailyPrecipitation)) == 9

    # A later fetch fills in the missing value.
    lohja = next(s for s in series if s.fmisid == "100963")
    lohja.values = [(date(2026, 9, 22), "2.4")]
    store_series(db, [lohja])
    row = db.execute(
        select(DailyPrecipitation).join(Station).where(Station.source_station_id == "100963", DailyPrecipitation.date == date(2026, 9, 22))
    ).scalar_one()
    db.refresh(row)
    assert (row.precipitation_mm, row.has_data, row.raw_status) == (2.4, True, "2.4")


def test_date_chunks():
    chunks = list(date_chunks(date(2025, 1, 1), date(2025, 3, 5), days=31))
    assert chunks[0] == (date(2025, 1, 1), date(2025, 1, 31))
    assert chunks[-1][1] == date(2025, 3, 5)
    assert all(b >= a for a, b in chunks)


def test_default_range(db):
    today = date(2026, 9, 25)
    assert default_range(db, date(2025, 1, 1), 10, today) == (date(2025, 1, 1), date(2026, 9, 24))
    store_series(db, parse_timevaluepair(FIXTURE))  # latest row 2026-09-22
    assert default_range(db, date(2025, 1, 1), 10, today) == (date(2026, 9, 12), date(2026, 9, 24))


def test_run_ingest_with_mocked_fmi(db):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(dict(request.url.params))
        return httpx.Response(200, content=FIXTURE)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        total = run_ingest(db, client, date(2026, 8, 1), date(2026, 9, 22))

    assert len(requests) == 2  # two 31-day chunks
    assert requests[0]["parameters"] == "rrday"
    assert requests[0]["starttime"] == "2026-08-01T00:00:00Z"
    assert total == 18

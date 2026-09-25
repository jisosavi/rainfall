from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.db.models import DailyValue, Station
from app.ingest import fmi
from app.ingest.common import date_chunks
from app.ingest.fmi import normalize, parse_timevaluepair
from app.ingest.service import default_range, run_ingest, store_series

FIXTURE = (Path(__file__).parent / "fixtures" / "fmi_daily_timevaluepair.xml").read_bytes()


def test_parse_real_fmi_response():
    stations = parse_timevaluepair(FIXTURE)
    by_id = {s.source_station_id: s for s in stations}
    assert set(by_id) == {"100908", "101049", "100963"}
    uto = by_id["100908"]
    assert uto.name == "Parainen Utö"
    assert uto.region == "Parainen"
    assert (uto.lat, uto.lon) == (59.77909, 21.37479)
    assert (uto.source, uto.country) == ("fmi", "FI")
    assert [d for d, _ in uto.values] == [date(2026, 9, 20), date(2026, 9, 21), date(2026, 9, 22)]
    assert [v.raw_status for _, v in by_id["100963"].values] == ["0.7", "0.0", "NaN"]
    assert [v.value for _, v in by_id["100963"].values] == [0.7, 0.0, None]


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
    assert (value.value, value.has_data) == expected
    assert value.raw_status == raw


def test_store_series_is_idempotent_and_updates(db):
    series = parse_timevaluepair(FIXTURE)
    assert store_series(db, series) == 9
    assert store_series(db, series) == 9
    assert db.scalar(select(func.count()).select_from(Station)) == 3
    assert db.scalar(select(func.count()).select_from(DailyValue)) == 9

    # A later fetch fills in the missing value.
    lohja = next(s for s in series if s.source_station_id == "100963")
    lohja.values = [(date(2026, 9, 22), normalize("2.4"))]
    store_series(db, [lohja])
    row = db.execute(
        select(DailyValue).join(Station).where(Station.source_station_id == "100963", DailyValue.date == date(2026, 9, 22))
    ).scalar_one()
    db.refresh(row)
    assert (row.value, row.has_data, row.raw_status) == (2.4, True, "2.4")


def test_date_chunks():
    chunks = list(date_chunks(date(2025, 1, 1), date(2025, 3, 5), days=31))
    assert chunks[0] == (date(2025, 1, 1), date(2025, 1, 31))
    assert chunks[-1][1] == date(2025, 3, 5)
    assert all(b >= a for a, b in chunks)


def test_default_range(db):
    today = date(2026, 9, 25)
    assert default_range(db, "fmi", date(2025, 1, 1), 10, today) == (date(2025, 1, 1), date(2026, 9, 24))
    store_series(db, parse_timevaluepair(FIXTURE))  # latest FMI row 2026-09-22
    assert default_range(db, "fmi", date(2025, 1, 1), 10, today) == (date(2026, 9, 12), date(2026, 9, 24))
    # Each source tracks its own progress.
    assert default_range(db, "met", date(2025, 1, 1), 10, today) == (date(2025, 1, 1), date(2026, 9, 24))


def test_run_ingest_with_mocked_fmi(db):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(dict(request.url.params))
        return httpx.Response(200, content=FIXTURE)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        total = run_ingest(db, lambda a, b: fmi.fetch_daily(client, a, b), date(2026, 8, 1), date(2026, 9, 22))

    assert len(requests) == 2  # two 31-day chunks
    assert requests[0]["parameters"] == "rrday,snow"
    assert requests[0]["starttime"] == "2026-08-01T00:00:00Z"
    assert total == 18


RAIN_SNOW = (Path(__file__).parent / "fixtures" / "fmi_daily_rain_snow.xml").read_bytes()


def test_parse_rain_and_snow_from_one_response():
    # Real FMI response, 10-12 Feb 2026: Helsinki Kaisaniemi and Sodankylä Tähtelä.
    series = {(s.source_station_id, s.parameter): s for s in parse_timevaluepair(RAIN_SNOW)}
    assert set(series) == {("100971", "precipitation"), ("100971", "snow_depth"), ("101932", "precipitation"), ("101932", "snow_depth")}
    assert [v.value for _, v in series[("100971", "precipitation")].values] == [1.0, 4.7, 0.7]
    assert [v.value for _, v in series[("100971", "snow_depth")].values] == [19.0, 19.0, 29.0]
    assert [v.value for _, v in series[("101932", "snow_depth")].values] == [75.0, 75.0, 75.0]
    # -1 means "no precipitation" here; for snow it would mean "no snow cover" (0 cm, has data).
    assert [(v.value, v.has_data) for _, v in series[("101932", "precipitation")].values] == [(0.0, True)] * 3


def test_rain_and_snow_stored_side_by_side(db):
    store_series(db, parse_timevaluepair(RAIN_SNOW))
    rows = db.execute(
        select(DailyValue.parameter, func.count()).group_by(DailyValue.parameter).order_by(DailyValue.parameter)
    ).all()
    assert rows == [("precipitation", 6), ("snow_depth", 6)]
    assert db.scalar(select(func.count()).select_from(Station)) == 2  # one station row per station


def test_default_range_backfills_a_newly_added_parameter(db):
    today = date(2026, 9, 25)
    store_series(db, [s for s in parse_timevaluepair(FIXTURE)])  # precipitation only, up to 2026-09-22
    both = ("precipitation", "snow_depth")
    assert default_range(db, "fmi", date(2025, 1, 1), 10, today, parameters=("precipitation",)) == (date(2026, 9, 12), date(2026, 9, 24))
    # Snow has no data yet, so the whole history is fetched (rain is simply re-fetched too).
    assert default_range(db, "fmi", date(2025, 1, 1), 10, today, parameters=both) == (date(2025, 1, 1), date(2026, 9, 24))

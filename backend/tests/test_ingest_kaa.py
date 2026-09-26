from datetime import date, datetime, timedelta

import httpx

from app.ingest import kaa
from app.ingest.common import Normalized

D = date(2026, 9, 20)

STATION_ROWS = [
    {"jaam_kood": "AJHARK01", "jaam_nimi": "Tallinn-Harku", "laiuskraad": 59.398, "pikkuskraad": 24.603,
     "korgus_merepinnast_m": 33.16, "element_kood": el, "vaatlus_periood_algus": "2025-11-15T00:00:00",
     "vaatlus_periood_lopp": "3999-12-31T23:59:00"}
    for el in ("PR1H", "TA", "DTAN", "DTAX", "DSND")
] + [
    # An earlier period of the same element: both count.
    {"jaam_kood": "AJHARK01", "jaam_nimi": "Tallinn-Harku", "laiuskraad": 59.398, "pikkuskraad": 24.603,
     "korgus_merepinnast_m": 33.16, "element_kood": "DSND", "vaatlus_periood_algus": "2024-11-02T06:00:00",
     "vaatlus_periood_lopp": "2025-04-15T06:00:00"},
    {"jaam_kood": "AJOLD001", "jaam_nimi": "Closed", "laiuskraad": 58.0, "pikkuskraad": 25.0,
     "korgus_merepinnast_m": 50.0, "element_kood": "PR1H", "vaatlus_periood_algus": "1991-01-01T00:00:00",
     "vaatlus_periood_lopp": "2010-12-31T23:59:00"},
]


def hourly(station, element, first: datetime, values):
    rows = []
    for i, v in enumerate(values):
        t = first + timedelta(hours=i)
        rows.append({"jaam_kood": station, "aasta": t.year, "kuu": t.month, "paev": t.day, "tund": t.hour,
                     "vaartus": v, "element_kood": element})
    return rows


def test_stations_with_height_and_periods():
    [harku, closed] = sorted(kaa.parse_stations(STATION_ROWS), key=lambda s: s.id)
    assert (harku.name, harku.elevation_m) == ("Tallinn-Harku", 33.16)
    assert set(harku.elements) == {"PR1H", "TA", "DTAN", "DTAX", "DSND"}
    assert kaa._observes(harku, "PR1H", D, D) and not kaa._observes(closed, "PR1H", D, D)
    assert kaa._observes(harku, "DSND", date(2025, 2, 10), date(2025, 2, 10))


def test_rain_is_summed_06_to_06_utc():
    # Hours ending 06 UTC on D (belongs to D-1) .. 07 UTC on D+1 (belongs to D+1).
    rows = hourly("AJHARK01", "PR1H", datetime(2026, 9, 20, 6), [9.0] + [0.5] * 24 + [9.0])
    values = kaa.rain_from_hours(rows, D, D)["AJHARK01"]
    assert values[D] == Normalized(12.0, True, "12.0|hourly24")
    # Only 17 hours so far (data up to 23 UTC): missing until the next day's data arrives.
    partial = kaa.rain_from_hours(hourly("AJHARK01", "PR1H", datetime(2026, 9, 20, 7), [0.1] * 17), D, D)
    assert partial["AJHARK01"][D] == Normalized(None, False, "hourly17")


def test_mean_from_readings_00_to_23_utc():
    rows = hourly("AJHARK01", "TA", datetime(2026, 9, 20, 0), [10.0] * 12 + [14.0] * 12 + [30.0])
    assert kaa.mean_from_hours(rows, D, D)["AJHARK01"][D] == Normalized(12.0, True, "12.0|hourly24")


def test_fetch_daily_queries_by_month_and_fills_missing_days():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/f_kliima_jaam_vaatlus"):
            return httpx.Response(200, json=STATION_ROWS)
        return httpx.Response(200, json=[
            {"jaam_kood": "AJHARK01", "aasta": 2026, "kuu": 1, "paev": 31, "vaartus": -21.4},
            {"jaam_kood": "AJHARK01", "aasta": 2026, "kuu": 2, "paev": 2, "vaartus": None},
        ])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        [series] = kaa.fetch_daily(client, date(2026, 1, 31), date(2026, 2, 2), parameter="temp_min")
    value_queries = [r.url.params for r in requests if r.url.path.endswith("/f_kliima_paev")]
    assert [(q["element_kood"], q["kuu"], q["and"]) for q in value_queries] == [
        ("eq.DTAN", "eq.1", "(paev.gte.31,paev.lte.31)"),
        ("eq.DTAN", "eq.2", "(paev.gte.1,paev.lte.2)"),
    ]
    assert (series.country, series.owner, series.elevation_m) == ("EE", "Keskkonnaagentuur", 33.16)
    assert [(d.isoformat(), v.value, v.has_data) for d, v in series.values] == [
        ("2026-01-31", -21.4, True), ("2026-02-01", None, False), ("2026-02-02", None, False),
    ]


def test_rain_fetch_includes_the_next_morning_and_hourly_confirmation():
    params = []

    def handler(request: httpx.Request) -> httpx.Response:
        params.append(request.url.params)
        return httpx.Response(200, json=hourly("AJHARK01", "PR1H", datetime(2026, 9, 20, 6), [1.0] * 26))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        hours = kaa.fetch_hourly_precipitation(client, "AJHARK01", D)
    assert params[0]["and"] == "(paev.gte.20,paev.lte.21)" and params[0]["jaam_kood"] == "eq.AJHARK01"
    assert len(hours) == 24  # ending 07 UTC on D .. 06 UTC on D+1

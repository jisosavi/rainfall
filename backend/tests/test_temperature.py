from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db.models import DailyValue
from app.ingest import dmi, fmi, imo, met, smhi
from app.ingest.common import Normalized, StationSeries, check_plausible
from app.ingest.service import store_series
from app.qc import RULES, find_suspects

D = date(2026, 1, 10)


def test_negative_temperatures_are_kept_and_limits_apply():
    assert check_plausible("temp_min", Normalized(-35.2, True, "-35.2")).value == -35.2
    assert check_plausible("temp_max", Normalized(-70.0, True, "-70.0")).has_data is False
    assert check_plausible("temp_max", Normalized(45.0, True, "45.0")).has_data is False
    assert check_plausible("precipitation", Normalized(-1.0, True, "-1")).has_data is False


def test_source_parsers_allow_negative_temperatures_only():
    # FMI's -1 means "no rain", not minus one degree.
    assert fmi.normalize("-1.0").value == 0.0
    assert fmi.normalize("-1.0", temperature=True).value == -1.0
    assert smhi.normalize("-12.5", "G").has_data is False
    assert smhi.normalize("-12.5", "G", allow_negative=True).value == -12.5
    assert met.parse_quality({"value": -8.1, "qualityCode": 0}).has_data is False
    assert met.parse_quality({"value": -8.1, "qualityCode": 0}, allow_negative=True).value == -8.1


def test_met_temperature_offsets():
    assert met.ELEMENTS["temp_mean"].time_offset == "PT0H"
    assert met.ELEMENTS["temp_min"].time_offset == met.ELEMENTS["temp_max"].time_offset == "PT18H"
    assert all(met.ELEMENTS[p].shift_days == 0 for p in ("temp_mean", "temp_min", "temp_max"))


def test_smhi_temperature_parameters():
    assert {p: smhi.PARAMETERS[p].number for p in ("temp_mean", "temp_min", "temp_max")} == {
        "temp_mean": 2,
        "temp_min": 19,
        "temp_max": 20,
    }


def _dmi_hours(station: str, first: datetime, values: list[float]) -> list[dict]:
    return [
        {
            "properties": {
                "stationId": station,
                "from": (first + timedelta(hours=i)).isoformat(),
                "to": (first + timedelta(hours=i + 1)).isoformat(),
                "value": v,
            }
        }
        for i, v in enumerate(values)
    ]


def test_dmi_mean_is_00_24_utc():
    midnight = datetime(2026, 1, 10, tzinfo=timezone.utc)
    # 24 hours at -2 on D, and a warm hour just after midnight that belongs to D+1.
    features = _dmi_hours("06180", midnight, [-2.0] * 24 + [10.0])
    values = dmi.temperature_from_hours(features, D, D, "temp_mean")["06180"]
    assert values[D] == Normalized(-2.0, True, "-2.0|hourly24")
    # Too few hours: missing.
    few = dmi.temperature_from_hours(_dmi_hours("x", midnight, [1.0] * 19), D, D, "temp_mean")
    assert few["x"][D] == Normalized(None, False, "hourly19")


def test_dmi_min_max_are_18_18_utc():
    evening = datetime(2026, 1, 9, 18, tzinfo=timezone.utc)
    # Hours starting 18 UTC on D-1 .. 17 UTC on D; the coldest is the first, and a colder
    # hour starting 18 UTC on D belongs to D+1.
    values = [-15.0] + [-5.0] * 23 + [-30.0]
    features = _dmi_hours("06180", evening, values)
    assert dmi.temperature_from_hours(features, D, D, "temp_min")["06180"][D].value == -15.0
    warm = _dmi_hours("06180", evening - timedelta(hours=1), [20.0] + [3.0] * 24)  # 17 UTC on D-1 is D-1's
    assert dmi.temperature_from_hours(warm, D, D, "temp_max")["06180"][D].value == 3.0


def test_dmi_fetch_requests_hourly_temperature_from_the_evening_before():
    import httpx

    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"features": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        dmi.fetch_daily(client, D, D, stations=[], parameter="temp_max")
    params = requests[0].url.params
    assert (params["parameterId"], params["timeResolution"]) == ("max_temp_w_date", "hour")
    assert params["datetime"] == "2026-01-09T18:00:00Z/2026-01-11T00:00:00Z"


def _imo_cube(code: str, first: datetime, values: list[float | None]) -> dict:
    times = [(first + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(len(values))]
    return {"coverages": [{"id": "1", "domain": {"axes": {"t": {"values": times}}}, "ranges": {code: {"values": values}}}]}


def test_imo_mean_from_on_the_hour_readings():
    cube = _imo_cube("t", datetime(2026, 1, 10, tzinfo=timezone.utc), [-4.0] * 12 + [-2.0] * 12 + [9.0])
    assert imo.parse_hourly_temperature([cube], D, D, "temp_mean")["1"][D] == Normalized(-3.0, True, "-3.0|hourly24")


def test_imo_min_max_hours_end_19_to_18_utc():
    # Timestamps mark the end of the hour: 18 UTC on D-1 closes D-1's window, 19 UTC opens D's.
    first = datetime(2026, 1, 9, 18, tzinfo=timezone.utc)
    cube = _imo_cube("tx", first, [8.0] + [1.0] * 24 + [7.0])
    assert imo.parse_hourly_temperature([cube], D, D, "temp_max")["1"][D].value == 1.0
    gaps = _imo_cube("tn", first, [None] * 4 + [-1.0] * 21)
    assert imo.parse_hourly_temperature([gaps], D, D, "temp_min")["1"][D].has_data is False


def test_imo_hour_cube_requests_three_days_at_a_time():
    import httpx

    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        imo.fetch_daily(client, date(2026, 1, 1), date(2026, 1, 7), stations=[], parameter="temp_min")
    windows = [r.url.params["datetime"] for r in requests]
    assert all(r.url.params["parameter-name"] == "tn" for r in requests)
    assert windows == [
        "2025-12-31T00:00:00Z/2026-01-02T23:00:00Z",
        "2026-01-03T00:00:00Z/2026-01-05T23:00:00Z",
        "2026-01-06T00:00:00Z/2026-01-07T23:00:00Z",
    ]


FMI_HOURLY = """<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2"
 xmlns:target="http://xml.fmi.fi/namespace/om/atmosphericfeatures/1.1" xmlns:wml2="http://www.opengis.net/waterml/2.0">
<wfs:member><target:Location>
 <gml:identifier codeSpace="http://xml.fmi.fi/namespace/stationcode/fmisid">100971</gml:identifier>
 <gml:name codeSpace="http://xml.fmi.fi/namespace/locationcode/name">Helsinki Kaisaniemi</gml:name>
 <target:region>Helsinki</target:region></target:Location>
 <gml:Point><gml:pos>60.17523 24.94459</gml:pos></gml:Point>
 {tvps}
</wfs:member></wfs:FeatureCollection>"""


def test_fmi_hourly_mean_hour_ending_midnight_belongs_to_the_day_before():
    first = datetime(2026, 1, 10, 1, tzinfo=timezone.utc)  # the hour 00–01 UTC
    values = [-10.0] * 24 + [5.0]  # ends 01 .. 24 UTC on D, then 01 UTC on D+1
    tvps = "".join(
        f"<wml2:MeasurementTVP><wml2:time>{(first + timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M:%SZ')}</wml2:time>"
        f"<wml2:value>{v}</wml2:value></wml2:MeasurementTVP>"
        for i, v in enumerate(values)
    )
    [series] = fmi.parse_hourly_mean(FMI_HOURLY.format(tvps=tvps), D, D)
    assert (series.parameter, series.source_station_id) == ("temp_mean", "100971")
    assert series.values == [(D, Normalized(-10.0, True, "-10.0|hourly24"))]


def test_negative_temperatures_are_stored(db):
    series = StationSeries(
        source="fmi", source_station_id="1", name="Enontekiö", region=None, lat=68.4, lon=23.6, country="FI",
        parameter="temp_min", values=[(D, Normalized(-41.3, True, "-41.3"))],
    )
    assert store_series(db, [series]) == 1
    assert db.execute(select(DailyValue.value)).scalar() == -41.3


def test_temperature_check_is_two_sided():
    a, b, c, d = (uuid4() for _ in range(4))
    positions = {a: (61.0, 25.0, 100.0), b: (61.1, 25.0, 90.0), c: (61.0, 25.2, 120.0), d: (60.9, 25.1, 80.0)}
    rule = RULES["temp_mean"]
    summer = {b: 15.0, c: 16.0, d: 14.0}
    assert find_suspects({a: 28.0, **summer}, positions, rule) == [a]  # 13 °C too warm
    assert find_suspects({a: 3.0, **summer}, positions, rule) == [a]  # 12 °C too cold
    assert find_suspects({a: 7.0, **summer}, positions, rule) == []
    # A cold hollow 12 °C below its neighbours' minimum is plausible.
    assert find_suspects({a: 1.0, b: 13.0, c: 14.0, d: 12.0}, positions, RULES["temp_min"]) == []
    # A mountain station isn't compared with the valley.
    high = {**positions, a: (61.0, 25.0, 900.0)}
    assert find_suspects({a: 3.0, **summer}, high, rule) == []


def test_winter_inversions_are_allowed_but_faults_are_not():
    a, b, c, d = (uuid4() for _ in range(4))
    positions = {a: (68.0, 21.0, 480.0), b: (68.1, 21.0, 500.0), c: (68.0, 21.2, 600.0), d: (67.9, 21.1, 450.0)}
    winter = {b: -22.0, c: -21.0, d: -23.0}
    # Like Kilpisjärvi village, 17 °C below the slopes in a January inversion: kept.
    assert find_suspects({a: -39.0, **winter}, positions, RULES["temp_min"]) == []
    assert find_suspects({a: -5.0, **winter}, positions, RULES["temp_mean"]) == []  # 17 °C warmer: kept
    # More than 20 °C off is still a fault, e.g. a road sensor reading -45 in a -20 spell.
    assert find_suspects({a: -45.0, **winter}, positions, RULES["temp_max"]) == [a]


def test_temperature_rankings(client, db):
    from tests.test_rankings import add_station, days

    month = days(date(2026, 1, 1), 10)
    # Kilpisjärvi-like: coldest night -39 on 5 Jan; its flagged -52 doesn't count.
    add_station(db, "Cold", "FI", {d: -20.0 for d in month} | {month[4]: -39.0, month[6]: -52.0},
                parameter="temp_min", flags={month[6]: "suspect_spatial"})
    add_station(db, "Mild", "NO", {d: -2.0 for d in month} | {month[2]: 1.5}, parameter="temp_min")
    add_station(db, "Short", "SE", {month[0]: -45.0}, parameter="temp_min")  # one day is enough for an extreme
    add_station(db, "Mean full", "FI", {d: -5.0 for d in month}, parameter="temp_mean")
    add_station(db, "Mean gappy", "FI", {d: -30.0 for d in month[:3]}, parameter="temp_mean")
    db.commit()
    params = {"parameter": "temp_min", "period": "month", "date": "2026-01-10"}

    coldest = client.get("/api/rankings", params={**params, "order": "coldest"}).json()
    assert [(s["name"], s["value"]) for s in coldest["stations"]] == [("Short", -45.0), ("Cold", -39.0), ("Mild", -2.0)]
    assert coldest["stations"][1]["on_date"] == "2026-01-05"
    assert (coldest["order"], coldest["min_coverage"]) == ("coldest", 0)

    warmest = client.get("/api/rankings", params=params).json()
    assert [(s["name"], s["value"], s["on_date"]) for s in warmest["stations"]][0] == ("Mild", 1.5, "2026-01-03")

    # Mean: the period's average, with the coverage rule.
    mean = client.get("/api/rankings", params={**params, "parameter": "temp_mean", "order": "coldest"}).json()
    assert [s["name"] for s in mean["stations"]] == ["Mean full"]
    everyone = client.get("/api/rankings", params={**params, "parameter": "temp_mean", "order": "coldest", "min_coverage": 0}).json()
    assert [s["name"] for s in everyone["stations"]] == ["Mean gappy", "Mean full"]

    wrong = client.get("/api/rankings", params={**params, "period": "winter_max"})
    assert wrong.status_code == 422


def test_changed_rules_are_rechecked_once(db):
    from app.qc import RULES_VERSION, mark_checked, stale_parameters

    assert set(stale_parameters(db)) == {p for p, v in RULES_VERSION.items() if v > 1}
    mark_checked(db, stale_parameters(db))
    assert stale_parameters(db) == []


def test_fmi_station_heights():
    import httpx

    def handler(request):
        assert request.url.params["keyword"] == "synop_fi"
        return httpx.Response(200, json=[
            {"fmisid": 101939, "elevation": 532.0}, {"fmisid": 101939, "elevation": 532.0}, {"fmisid": 1, "elevation": None},
        ])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        heights = fmi.fetch_elevations(client)
    assert heights == {"101939": 532.0}
    series = StationSeries(source="fmi", source_station_id="101939", name="Sodankylä Luosto", region=None,
                           lat=67.1, lon=26.9, country="FI", parameter="temp_min")
    assert fmi.with_elevations([series], heights)[0].elevation_m == 532.0

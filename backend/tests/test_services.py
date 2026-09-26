from datetime import date, datetime, timedelta, timezone

import pytest

from app.db.models import DailyValue, Station
from app.services import overview, stations
from app.services.errors import InvalidRequestError, NotFoundError

TODAY = date.today()


def station(db, name, country, lat, lon, source="fmi", elevation=None, region=None):
    s = Station(source=source, source_station_id=name, name=name, lat=lat, lon=lon, country=country,
                elevation_m=elevation, region=region)
    db.add(s)
    db.flush()
    return s


def values(db, s, parameter, by_day, flags=None):
    for day, value in by_day.items():
        db.add(DailyValue(station_id=s.id, parameter=parameter, date=day, value=value, has_data=value is not None,
                          flag=(flags or {}).get(day), fetched_at=datetime(2026, 9, 26, 7, 20, tzinfo=timezone.utc)))


@pytest.fixture
def nordic(db):
    d = TODAY - timedelta(days=2)
    helsinki = station(db, "Helsinki Kaisaniemi", "FI", 60.175, 24.944, elevation=4, region="Helsinki")
    vantaa = station(db, "Vantaa lentoasema", "FI", 60.327, 24.957, region="Vantaa")
    tallinn = station(db, "Tallinn-Harku", "EE", 59.398, 24.603, source="kaa", elevation=33)
    oslo = station(db, "Oslo - Blindern", "NO", 59.942, 10.720, source="met")
    values(db, helsinki, "precipitation", {d - timedelta(days=1): 2.0, d: 12.5})
    values(db, helsinki, "temp_min", {d: -3.0})
    values(db, vantaa, "precipitation", {d: 80.0}, flags={d: "suspect_spatial"})
    values(db, vantaa, "temp_min", {d: -8.5})
    values(db, tallinn, "precipitation", {d: None})
    values(db, tallinn, "temp_min", {d: -1.0})
    values(db, oslo, "snow_depth", {d: 10.0})
    db.commit()
    return {"day": d, "helsinki": helsinki, "vantaa": vantaa, "tallinn": tallinn, "oslo": oslo}


def test_find_near_a_point_nearest_first_with_distance(db, nordic):
    found = stations.find_stations(db, lat=60.17, lon=24.94, radius_km=100)
    assert [s.name for s in found] == ["Helsinki Kaisaniemi", "Vantaa lentoasema", "Tallinn-Harku"]
    assert found[0].distance_km < 1 and 80 < found[2].distance_km < 90
    assert found[0].measurements == ["precipitation", "temp_min"]
    only_ee = stations.find_stations(db, lat=60.17, lon=24.94, radius_km=100, countries=["EE"])
    assert [s.name for s in only_ee] == ["Tallinn-Harku"]


def test_find_by_name_or_municipality_and_measurement(db, nordic):
    assert [s.name for s in stations.find_stations(db, name="vantaa")] == ["Vantaa lentoasema"]
    assert [s.name for s in stations.find_stations(db, name="oslo", parameter="snow_depth")] == ["Oslo - Blindern"]
    assert stations.find_stations(db, name="oslo", parameter="temp_min") == []
    with pytest.raises(InvalidRequestError):
        stations.find_stations(db)
    with pytest.raises(InvalidRequestError):
        stations.find_stations(db, lat=60.0)


def test_station_info_coverage(db, nordic):
    info = stations.station_info(db, nordic["helsinki"].id)
    assert (info.elevation_m, info.region) == (4, "Helsinki")
    rain = next(c for c in info.coverage if c.parameter == "precipitation")
    assert (rain.first_date, rain.last_date, rain.days_with_data, rain.unit) == (nordic["day"] - timedelta(days=1), nordic["day"], 2, "mm")
    with pytest.raises(NotFoundError):
        stations.station_info(db, nordic["helsinki"].id.__class__(int=1))


def test_observations_summary_leaves_out_flagged_values(db, nordic):
    d = nordic["day"]
    obs = stations.observations(db, nordic["vantaa"].id, ["precipitation", "temp_min"], d - timedelta(days=1), d)
    rain, cold = obs.series
    assert (rain.summary.flagged, rain.summary.days_with_data, rain.summary.total) == (1, 0, None)
    assert rain.values[0].value == 80.0  # still listed, marked
    assert (cold.summary.min, cold.summary.min_date, cold.summary.days) == (-8.5, d, 2)
    helsinki = stations.observations(db, nordic["helsinki"].id, ["precipitation"], None, None)
    assert (helsinki.start, helsinki.end) == (d - timedelta(days=29), d)
    assert (helsinki.series[0].summary.total, helsinki.series[0].summary.days_at_least_1) == (14.5, 2)
    with pytest.raises(InvalidRequestError):
        stations.observations(db, nordic["helsinki"].id, ["precipitation"], d - timedelta(days=400), d)


def test_day_overview_by_country_and_area(db, nordic):
    d = nordic["day"]
    rain = overview.day_overview(db, d, "precipitation", country="fi")
    assert (rain.stations, rain.reporting, rain.flagged) == (2, 2, 1)
    assert rain.max.name == "Helsinki Kaisaniemi" and rain.lowest == []
    cold = overview.day_overview(db, None, "temp_min", top=2)
    assert [v.name for v in cold.lowest] == ["Vantaa lentoasema", "Helsinki Kaisaniemi"]
    assert (cold.min.value, cold.max.value, cold.median) == (-8.5, -1.0, -3.0)
    gulf = overview.day_overview(db, d, "temp_min", bbox=(24.0, 59.0, 25.0, 60.25))
    assert {v.name for v in gulf.highest} == {"Tallinn-Harku", "Helsinki Kaisaniemi"}
    with pytest.raises(InvalidRequestError):
        overview.day_overview(db, d, "precipitation", country="xx")


def test_data_status_per_source(db, nordic):
    status = overview.data_status(db)
    by_source = {s.source: s for s in status.sources}
    assert by_source["fmi"].latest_date == {"precipitation": nordic["day"], "temp_min": nordic["day"]}
    assert "precipitation" not in by_source["kaa"].latest_date  # only a missing row
    assert by_source["met"].latest_date == {"snow_depth": nordic["day"]}
    assert status.updated_at is not None

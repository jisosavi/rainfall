from datetime import date, timedelta

from app.api.routes.rankings import period_range
from app.db.models import DailyValue, Station


def add_station(db, name, country, values, parameter="precipitation", flags=None):
    station = Station(source="fmi", source_station_id=name, name=name, lat=61.0, lon=25.0, country=country)
    db.add(station)
    db.flush()
    for day, value in values.items():
        db.add(DailyValue(
            station_id=station.id, parameter=parameter, date=day, value=value, has_data=value is not None,
            flag=(flags or {}).get(day),
        ))
    return station


def days(start, n):
    return [start + timedelta(days=i) for i in range(n)]


def test_period_ranges():
    assert period_range("week", date(2026, 9, 24)) == (date(2026, 9, 21), date(2026, 9, 24))  # Monday
    assert period_range("month", date(2026, 9, 24)) == (date(2026, 9, 1), date(2026, 9, 24))
    assert period_range("year", date(2026, 9, 24)) == (date(2026, 1, 1), date(2026, 9, 24))
    assert period_range("last30", date(2026, 9, 24)) == (date(2026, 8, 26), date(2026, 9, 24))
    assert period_range("winter_max", date(2026, 2, 10)) == (date(2025, 10, 1), date(2026, 2, 10))
    assert period_range("winter_days", date(2026, 11, 5)) == (date(2026, 10, 1), date(2026, 11, 5))


def test_rain_totals_coverage_and_flags(client, db):
    month = days(date(2026, 9, 1), 10)  # rank for 1-10 Sept: 10 days
    add_station(db, "Wet", "NO", {d: 5.0 for d in month})  # 50 mm, full coverage
    add_station(db, "Gappy", "SE", {d: 20.0 for d in month[:5]})  # 100 mm but only 50% coverage
    add_station(db, "Storm", "FI", {d: 1.0 for d in month} | {month[3]: 90.0},
                flags={month[3]: "suspect_spatial"})  # the 90 mm day doesn't count
    add_station(db, "Real storm", "FI", {d: 1.0 for d in month} | {month[3]: 60.0},
                flags={month[3]: "confirmed_hourly"})  # confirmed: counts
    db.commit()

    body = client.get("/api/rankings", params={"period": "month", "date": "2026-09-10"}).json()
    assert (body["start"], body["days"], body["unit"]) == ("2026-09-01", 10, "mm")
    # Gappy (50% coverage) is left out. Storm: 9 of 10 days count (flagged day is missing),
    # exactly the 90% needed, with 9 mm.
    assert [(s["name"], s["value"]) for s in body["stations"]] == [("Real storm", 69.0), ("Wet", 50.0), ("Storm", 9.0)]
    everyone = client.get("/api/rankings", params={"period": "month", "date": "2026-09-10", "min_coverage": 0}).json()
    assert [s["name"] for s in everyone["stations"]] == ["Gappy", "Real storm", "Wet", "Storm"]
    storm = everyone["stations"][-1]
    assert (storm["value"], storm["days_with_data"], storm["coverage"]) == (9.0, 9, 0.9)

    finland = client.get("/api/rankings", params={"period": "month", "date": "2026-09-10", "country": "fi"}).json()
    assert [s["name"] for s in finland["stations"]] == ["Real storm", "Storm"]
    assert finland["stations"][0]["rank"] == 1


def test_snow_rankings(client, db):
    winter = days(date(2025, 12, 1), 5)
    add_station(db, "Deep", "NO", {winter[0]: 120.0, winter[4]: 80.0}, parameter="snow_depth")
    add_station(db, "Steady", "SE", {d: 30.0 for d in winter}, parameter="snow_depth")
    db.commit()
    now = client.get("/api/rankings", params={"parameter": "snow_depth", "period": "now", "date": "2025-12-05"}).json()
    assert [(s["name"], s["value"]) for s in now["stations"]] == [("Deep", 80.0), ("Steady", 30.0)]
    deepest = client.get("/api/rankings", params={"parameter": "snow_depth", "period": "winter_max", "date": "2025-12-05"}).json()
    assert deepest["stations"][0]["value"] == 120.0 and deepest["min_coverage"] == 0
    snow_days = client.get(
        "/api/rankings", params={"parameter": "snow_depth", "period": "winter_days", "date": "2025-12-05", "min_coverage": 0}
    ).json()
    assert [(s["name"], s["value"]) for s in snow_days["stations"]] == [("Steady", 5.0), ("Deep", 2.0)]


def test_invalid_combinations(client):
    assert client.get("/api/rankings", params={"period": "now", "date": "2026-01-01"}).status_code == 422
    assert client.get("/api/rankings", params={"parameter": "snow_depth", "period": "month", "date": "2026-01-01"}).status_code == 422
    assert client.get("/api/rankings", params={"period": "month", "date": "2026-01-01", "country": "xx"}).status_code == 422

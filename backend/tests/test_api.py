from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db.models import DailyValue


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_latest_date_empty_db(client):
    assert client.get("/api/latest-date").status_code == 404


def test_latest_date_ignores_missing_only_days(client, seeded):
    assert client.get("/api/latest-date").json() == {"date": "2026-09-24"}


def test_stations_defaults_to_latest_and_includes_no_data_stations(client, seeded):
    body = client.get("/api/stations").json()
    assert body["date"] == "2026-09-24"
    by_name = {s["name"]: s for s in body["stations"]}
    assert set(by_name) == {"Helsinki Kaisaniemi", "Oulu lentoasema"}  # inactive excluded
    assert by_name["Helsinki Kaisaniemi"]["precipitation_mm"] == 4.5
    assert by_name["Helsinki Kaisaniemi"]["has_data"] is True
    assert by_name["Oulu lentoasema"]["has_data"] is False
    assert by_name["Oulu lentoasema"]["precipitation_mm"] is None
    assert by_name["Oulu lentoasema"]["source"] == "fmi"
    assert by_name["Oulu lentoasema"]["owner"] is None


def test_stations_only_includes_stations_reported_that_day(client, seeded):
    body = client.get("/api/stations", params={"date": "2025-12-31"}).json()
    assert [s["name"] for s in body["stations"]] == ["Helsinki Kaisaniemi"]
    assert client.get("/api/stations", params={"date": "2026-01-01"}).json()["stations"] == []


def test_stations_rejects_bad_date(client, seeded):
    assert client.get("/api/stations", params={"date": "yesterday"}).status_code == 422


def test_station_detail(client, seeded):
    station_id = seeded["helsinki"].id
    body = client.get(f"/api/stations/{station_id}", params={"date": "2025-12-31"}).json()
    assert body["precipitation_mm"] == 1.2
    assert body["date"] == "2025-12-31"


def test_station_detail_not_found_and_invalid_id(client, seeded):
    assert client.get(f"/api/stations/{uuid4()}").status_code == 404
    assert client.get("/api/stations/not-a-uuid").status_code == 422


def test_dates_and_years(client, seeded):
    assert client.get("/api/dates").json() == {"dates": ["2026-09-24", "2025-12-31"]}
    assert client.get("/api/dates", params={"year": 2025}).json() == {"dates": ["2025-12-31"]}
    assert client.get("/api/years").json() == {"years": [2025, 2026]}


def test_check_constraint_rejects_inconsistent_row(db, seeded):
    db.add(DailyValue(station_id=seeded["oulu"].id, date=date(2026, 1, 2), value=None, has_data=True))
    with pytest.raises(IntegrityError):
        db.commit()


def test_unique_station_date(db, seeded):
    db.add(DailyValue(station_id=seeded["helsinki"].id, date=date(2026, 9, 24), value=1.0, has_data=True))
    with pytest.raises(IntegrityError):
        db.commit()


def test_settings_parse_railway_values(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/railway")
    monkeypatch.setenv("CORS_ORIGINS", "https://isosavi.com, https://www.isosavi.com")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+psycopg://u:p@host:5432/railway"
    assert settings.cors_origins == ["https://isosavi.com", "https://www.isosavi.com"]


def test_station_history(client, seeded):
    station_id = seeded["helsinki"].id
    body = client.get(f"/api/stations/{station_id}/history").json()
    assert (body["start"], body["end"]) == ("2026-08-26", "2026-09-24")
    assert body["values"] == [{"date": "2026-09-24", "value": 4.5, "precipitation_mm": 4.5, "has_data": True, "flag": None}]
    assert (body["parameter"], body["unit"]) == ("precipitation", "mm")

    body = client.get(f"/api/stations/{station_id}/history", params={"start": "2025-12-01", "end": "2026-09-30"}).json()
    assert [v["date"] for v in body["values"]] == ["2025-12-31", "2026-09-24"]


def test_station_history_validation(client, seeded):
    station_id = seeded["helsinki"].id
    assert client.get(f"/api/stations/{uuid4()}/history").status_code == 404
    assert client.get(f"/api/stations/{station_id}/history", params={"start": "2026-02-01", "end": "2026-01-01"}).status_code == 422
    assert client.get(f"/api/stations/{station_id}/history", params={"start": "2024-01-01", "end": "2026-01-01"}).status_code == 422


def test_snow_depth_parameter(client, db, seeded):
    from app.db.models import SNOW_DEPTH

    db.add(DailyValue(station_id=seeded["helsinki"].id, parameter=SNOW_DEPTH, date=date(2026, 2, 10), value=19.0, has_data=True))
    db.add(DailyValue(station_id=seeded["oulu"].id, parameter=SNOW_DEPTH, date=date(2026, 2, 10), value=0.0, has_data=True))
    db.commit()

    body = client.get("/api/stations", params={"parameter": "snow_depth"}).json()
    assert (body["date"], body["parameter"], body["unit"]) == ("2026-02-10", "snow_depth", "cm")
    by_name = {s["name"]: s for s in body["stations"]}
    assert by_name["Helsinki Kaisaniemi"]["value"] == 19.0
    assert by_name["Helsinki Kaisaniemi"]["precipitation_mm"] is None  # compat field is rain-only
    assert by_name["Oulu lentoasema"]["value"] == 0.0

    # Rain endpoints are unaffected by snow rows.
    assert client.get("/api/latest-date").json() == {"date": "2026-09-24"}
    assert client.get("/api/latest-date", params={"parameter": "snow_depth"}).json() == {"date": "2026-02-10"}
    assert client.get("/api/stations", params={"date": "2026-02-10"}).json()["stations"] == []

    history = client.get(
        f"/api/stations/{seeded['helsinki'].id}/history", params={"parameter": "snow_depth", "start": "2025-10-01", "end": "2026-02-28"}
    ).json()
    assert [(v["date"], v["value"]) for v in history["values"]] == [("2026-02-10", 19.0)]
    assert client.get("/api/dates", params={"parameter": "snow_depth"}).json() == {"dates": ["2026-02-10"]}
    assert client.get("/api/stations", params={"parameter": "rain"}).status_code == 422


def test_status_reports_last_fetch(client, seeded):
    body = client.get("/api/status").json()
    assert set(body["sources"]) == {"fmi"}
    assert body["updated_at"] == body["sources"]["fmi"]


def test_status_empty_db(client):
    assert client.get("/api/status").json() == {"updated_at": None, "sources": {}}

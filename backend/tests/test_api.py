from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db.models import DailyPrecipitation


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


def test_stations_for_date_without_rows_returns_all_hollow(client, seeded):
    body = client.get("/api/stations", params={"date": "2026-01-01"}).json()
    assert len(body["stations"]) == 2
    assert all(not s["has_data"] for s in body["stations"])


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
    db.add(DailyPrecipitation(station_id=seeded["oulu"].id, date=date(2026, 1, 2), precipitation_mm=None, has_data=True))
    with pytest.raises(IntegrityError):
        db.commit()


def test_unique_station_date(db, seeded):
    db.add(DailyPrecipitation(station_id=seeded["helsinki"].id, date=date(2026, 9, 24), precipitation_mm=1.0, has_data=True))
    with pytest.raises(IntegrityError):
        db.commit()


def test_settings_parse_railway_values(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/railway")
    monkeypatch.setenv("CORS_ORIGINS", "https://isosavi.com, https://www.isosavi.com")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+psycopg://u:p@host:5432/railway"
    assert settings.cors_origins == ["https://isosavi.com", "https://www.isosavi.com"]

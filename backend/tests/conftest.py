from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import DailyPrecipitation, Station
from app.db.session import get_db
from app.main import app


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(db):
    helsinki = Station(source_station_id="100971", name="Helsinki Kaisaniemi", lat=60.175, lon=24.944, region="Uusimaa")
    oulu = Station(source_station_id="101786", name="Oulu lentoasema", lat=64.93, lon=25.354, region="Pohjois-Pohjanmaa")
    retired = Station(source_station_id="999999", name="Retired", lat=61.0, lon=25.0, active=False)
    db.add_all([helsinki, oulu, retired])
    db.flush()
    db.add_all(
        [
            DailyPrecipitation(station_id=helsinki.id, date=date(2025, 12, 31), precipitation_mm=1.2, has_data=True),
            DailyPrecipitation(station_id=helsinki.id, date=date(2026, 9, 24), precipitation_mm=4.5, has_data=True),
            DailyPrecipitation(station_id=oulu.id, date=date(2026, 9, 24), precipitation_mm=None, has_data=False),
            # A day with only missing data must not count as an available date.
            DailyPrecipitation(station_id=oulu.id, date=date(2026, 9, 25), precipitation_mm=None, has_data=False),
        ]
    )
    db.commit()
    return {"helsinki": helsinki, "oulu": oulu, "retired": retired}

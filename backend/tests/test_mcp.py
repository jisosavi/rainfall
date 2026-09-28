from datetime import date, timedelta

import pytest
from mcp.client import Client
from sqlalchemy.orm import sessionmaker

from app.db import session as db_session
from app.mcp_server.server import ATTRIBUTION, mcp
from tests.test_services import nordic, station, values  # noqa: F401 (fixture)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def tools_db(db, monkeypatch):
    # Tools open their own sessions: point them at the test database.
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(bind=db.get_bind()))
    return db


async def call(name, **arguments):
    async with Client(mcp) as client:
        return await client.call_tool(name, arguments)


async def test_lists_read_only_tools_resource_and_prompt():
    async with Client(mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        assert set(tools) == {"find_stations", "get_station", "get_observations", "get_day_overview", "get_rankings", "get_data_status"}
        assert all(t.annotations.read_only_hint for t in tools.values())
        assert tools["get_rankings"].output_schema is not None
        resources = (await client.list_resources()).resources
        assert [str(r.uri) for r in resources] == ["weather://conventions"]
        text = (await client.read_resource("weather://conventions")).contents[0].text
        assert "06 UTC on D to 06 UTC on D+1" in text
        prompts = (await client.list_prompts()).prompts
        assert [p.name for p in prompts] == ["weather_summary"]


async def test_find_stations_and_observations(tools_db, nordic):
    found = await call("find_stations", lat=60.17, lon=24.94, radius_km=30)
    data = found.structured_content
    assert [s["name"] for s in data["stations"]] == ["Helsinki Kaisaniemi", "Vantaa lentoasema"]
    assert data["attribution"] == ATTRIBUTION
    helsinki = data["stations"][0]["id"]
    obs = (await call("get_observations", station_id=helsinki, measurements=["precipitation"], summary_only=True)).structured_content
    assert obs["series"][0]["summary"]["total"] == 14.5 and obs["series"][0]["values"] == []


async def test_day_overview_rankings_and_status(tools_db, nordic):
    day = nordic["day"].isoformat()
    cold = (await call("get_day_overview", measurement="temp_min", date=day, top=2)).structured_content
    assert cold["lowest"][0]["name"] == "Vantaa lentoasema"
    ranked = (await call("get_rankings", measurement="temp_min", period="now", date=day, order="coldest")).structured_content
    assert [s["name"] for s in ranked["stations"]][:2] == ["Vantaa lentoasema", "Helsinki Kaisaniemi"]
    status = (await call("get_data_status")).structured_content
    assert {s["source"] for s in status["sources"]} == {"fmi", "kaa", "met"}


async def test_errors_are_readable(tools_db, nordic):
    missing = await call("get_station", station_id="00000000-0000-0000-0000-000000000001")
    assert missing.is_error and "Station not found" in missing.content[0].text
    too_long = await call(
        "get_observations", station_id=str(nordic["helsinki"].id), measurements=["temp_min"],
        start=(nordic["day"] - timedelta(days=500)).isoformat(),
    )
    assert too_long.is_error and "366 days" in too_long.content[0].text
    area = await call("get_day_overview", measurement="temp_min", min_lon=20.0)
    assert area.is_error and "all four" in area.content[0].text
    wrong_period = await call("get_rankings", measurement="temp_min", period="winter_max", date=date.today().isoformat())
    assert wrong_period.is_error and "doesn't apply" in wrong_period.content[0].text


async def test_rankings_in_an_area_across_borders(tools_db, nordic):
    day = nordic["day"].isoformat()
    # Around the Gulf of Finland: Helsinki and Tallinn, not Vantaa (north of 60.25) or Oslo.
    gulf = (await call(
        "get_rankings", measurement="temp_min", period="now", date=day, order="coldest",
        min_lon=24.0, min_lat=59.0, max_lon=25.5, max_lat=60.25,
    )).structured_content
    assert [s["name"] for s in gulf["stations"]] == ["Helsinki Kaisaniemi", "Tallinn-Harku"]
    half = await call("get_rankings", measurement="temp_min", period="now", date=day, min_lon=24.0)
    assert half.is_error and "all four" in half.content[0].text

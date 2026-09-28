import pytest
from mcp.client import Client
from sqlalchemy import select

from app.db.models import McpUsage
from app.limits import McpLimiter, McpLimits
from app.mcp_server import server, usage as usage_module
from app.mcp_server.usage import UsageCounts, caller_code
from tests.test_mcp import tools_db  # noqa: F401 (fixture)
from tests.test_services import nordic  # noqa: F401 (fixture)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fresh_usage(monkeypatch):
    counts = UsageCounts()
    monkeypatch.setattr(usage_module, "usage", counts)
    return counts


async def test_calls_are_counted_per_tool_and_stored(tools_db, nordic, fresh_usage, client):
    async with Client(server.mcp) as c:
        await c.call_tool("find_stations", {"name": "Helsinki"})
        await c.call_tool("find_stations", {"name": "Vantaa"})
        await c.call_tool("get_station", {"station_id": "00000000-0000-0000-0000-000000000001"})  # not found
    fresh_usage.flush()
    rows = {r.tool: r for r in tools_db.execute(select(McpUsage)).scalars()}
    assert (rows["find_stations"].calls, rows["find_stations"].errors) == (2, 0)
    assert (rows["get_station"].calls, rows["get_station"].errors) == (1, 1)
    fresh_usage.add("find_stations", "ok", 5)
    fresh_usage.flush()  # adds to the stored row
    tools_db.expire_all()
    assert tools_db.get(McpUsage, (rows["find_stations"].day, "find_stations")).calls == 3
    status = client.get("/api/status").json()["mcp_usage"]["today"]
    assert (status["calls"], status["errors"], status["by_tool"]["find_stations"]) == (4, 1, 3)


async def test_refused_calls_are_counted_not_run(tools_db, nordic, fresh_usage, monkeypatch):
    monkeypatch.setattr(server, "limiter", McpLimiter(McpLimits(global_per_minute=1)))
    async with Client(server.mcp) as c:
        await c.call_tool("find_stations", {"name": "Helsinki"})
        refused = await c.call_tool("find_stations", {"name": "Helsinki"})
    assert refused.is_error and "paused" in refused.content[0].text
    counts = fresh_usage.pending[next(iter(fresh_usage.pending))]
    assert (counts["calls"], counts["refused"]) == (1, 1)


def test_caller_code_hides_the_address():
    code = caller_code("203.0.113.9")
    assert code == caller_code("203.0.113.9") and len(code) == 10 and "203" not in code
    assert code != caller_code("203.0.113.10")
    assert caller_code(None) == "-"

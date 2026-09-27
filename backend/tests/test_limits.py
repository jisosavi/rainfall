import pytest
from mcp.client import Client

from app import main
from app.limits import LimitExceeded, McpLimiter, McpLimits, RestLimiter, client_ip
from app.mcp_server import server


class Clock:
    def __init__(self, now=1_800_000_000.0):  # the start of a clock minute
        self.now = now

    def __call__(self):
        return self.now


def limiter(clock, **limits):
    return McpLimiter(McpLimits(**limits), clock=clock)


def test_session_limit_per_minute_and_day():
    clock = Clock()
    lim = limiter(clock, session_per_minute=3, session_per_day=5, ip_per_minute=100)
    for _ in range(3):
        lim.check("s1", "1.2.3.4")
    with pytest.raises(LimitExceeded, match="this session"):
        lim.check("s1", "1.2.3.4")
    lim.check("s2", "1.2.3.4")  # another session is fine
    clock.now += 60
    lim.check("s1", "1.2.3.4")  # new minute (the refused call didn't count towards the day)
    with pytest.raises(LimitExceeded, match="daily limit"):
        clock.now += 60
        lim.check("s1", "1.2.3.4")
        lim.check("s1", "1.2.3.4")


def test_ip_limit_is_higher_for_anthropic():
    clock = Clock()
    lim = limiter(clock, ip_per_minute=2, trusted_ip_per_minute=5, session_per_minute=100)
    lim.check("a", "5.6.7.8")
    lim.check("b", "5.6.7.8")
    with pytest.raises(LimitExceeded, match="this address"):
        lim.check("c", "5.6.7.8")
    for i in range(5):  # Claude connector traffic: many sessions, one shared range
        lim.check(f"claude{i}", "160.79.105.12")
    with pytest.raises(LimitExceeded):
        lim.check("claude9", "160.79.105.12")


def test_global_overload_pauses_everyone_then_recovers():
    clock = Clock()
    lim = limiter(clock, global_per_minute=4, pause_minutes=15)
    for i in range(4):
        lim.check(f"s{i}", f"10.0.0.{i}")
    with pytest.raises(LimitExceeded, match="paused because of unusually high traffic") as paused:
        lim.check("s9", "10.0.0.9")
    assert paused.value.retry_after == 15 * 60 + 1
    clock.now += 14 * 60
    with pytest.raises(LimitExceeded, match="try again after"):
        lim.check("new", "10.0.1.1")
    clock.now += 61
    lim.check("new", "10.0.1.1")  # pause over


def test_client_ip_prefers_what_the_proxy_saw():
    assert client_ip({"x-real-ip": "9.9.9.9", "x-forwarded-for": "1.1.1.1, 9.9.9.9"}) == "9.9.9.9"
    assert client_ip({"x-forwarded-for": "6.6.6.6 (fake), 2.2.2.2"}) == "2.2.2.2"
    assert client_ip({}, "127.0.0.1") == "127.0.0.1"


def test_rest_api_limit_answers_429(client, monkeypatch):
    monkeypatch.setattr(main, "rest_limiter", RestLimiter(2))
    headers = {"x-real-ip": "7.7.7.7"}
    assert client.get("/api/years", headers=headers).status_code == 200
    assert client.get("/api/years", headers=headers).status_code == 200
    refused = client.get("/api/years", headers=headers)
    assert refused.status_code == 429 and int(refused.headers["retry-after"]) >= 1
    assert client.get("/api/years", headers={"x-real-ip": "8.8.8.8"}).status_code == 200
    assert client.get("/health").status_code == 200  # not limited


@pytest.mark.anyio
async def test_paused_tools_explain_when_to_retry(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(server, "limiter", limiter(clock, global_per_minute=1))
    async with Client(server.mcp) as client:
        await client.call_tool("get_data_status", {})  # may fail on the empty db; it still counts
        result = await client.call_tool("get_data_status", {})
    assert result.is_error and "paused because of unusually high traffic" in result.content[0].text


@pytest.fixture
def anyio_backend():
    return "asyncio"

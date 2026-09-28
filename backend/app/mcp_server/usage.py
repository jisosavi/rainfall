"""Traffic limits and usage tracking for MCP tool calls, as MCP server middleware.

Every tools/call passes through `limit_and_record`: the traffic limits are checked first (a
refused call never reaches the tool), then the call runs and is logged and counted.

- Log line per call: tool, a short summary of its arguments, duration, outcome and a caller
  code: a hash of the caller's IP with a salt that changes every UTC day and is only kept in
  memory, so callers can be told apart within a day but IP addresses are neither stored nor
  recoverable.
- Counts per UTC day and tool (calls, errors, refused, total duration) in memory, added to the
  mcp_usage table at most once a minute and when the app stops. No caller data is stored.
"""

import hashlib
import json
import logging
import secrets
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

import anyio
from sqlalchemy import select

from app.db import session as db_session
from app.db.models import McpUsage
from app.limits import LimitExceeded, McpLimiter, client_ip

logger = logging.getLogger("app.mcp")

FLUSH_SECONDS = 60
ARGUMENT_SUMMARY_CHARS = 200


def _today() -> date:
    return datetime.now(timezone.utc).date()


class _Salt:
    """A random salt per UTC day, never written anywhere."""

    def __init__(self):
        self.day: date | None = None
        self.value = ""

    def get(self) -> str:
        today = _today()
        if today != self.day:
            self.day, self.value = today, secrets.token_hex(16)
        return self.value


_salt = _Salt()


def caller_code(ip: str | None) -> str:
    if not ip:
        return "-"
    return hashlib.sha256(f"{_salt.get()}:{ip}".encode()).hexdigest()[:10]


class UsageCounts:
    """Counts per (day, tool) since the last flush."""

    def __init__(self):
        self.lock = threading.Lock()
        self.pending: dict[tuple[date, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.last_flush = time.monotonic()

    def add(self, tool: str, outcome: str, ms: int) -> None:
        with self.lock:
            counts = self.pending[(_today(), tool)]
            if outcome == "refused":
                counts["refused"] += 1
            else:
                counts["calls"] += 1
                counts["total_ms"] += ms
                if outcome == "error":
                    counts["errors"] += 1

    def due(self) -> bool:
        return time.monotonic() - self.last_flush >= FLUSH_SECONDS and bool(self.pending)

    def take(self) -> dict[tuple[date, str], dict[str, int]]:
        with self.lock:
            pending, self.pending = self.pending, defaultdict(lambda: defaultdict(int))
            self.last_flush = time.monotonic()
            return pending

    def flush(self) -> None:
        """Add pending counts to mcp_usage (runs in a worker thread)."""
        pending = self.take()
        if not pending:
            return
        db = db_session.SessionLocal()
        try:
            for (day, tool), counts in pending.items():
                row = db.execute(select(McpUsage).where(McpUsage.day == day, McpUsage.tool == tool)).scalar_one_or_none()
                if row is None:
                    row = McpUsage(day=day, tool=tool, calls=0, errors=0, refused=0, total_ms=0)
                    db.add(row)
                for field in ("calls", "errors", "refused", "total_ms"):
                    setattr(row, field, getattr(row, field) + counts.get(field, 0))
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("mcp usage: couldn't store counts")
        finally:
            db.close()


usage = UsageCounts()


def _summary(arguments: Any) -> str:
    text = json.dumps(arguments or {}, ensure_ascii=False, default=str, separators=(",", ":"))
    return text if len(text) <= ARGUMENT_SUMMARY_CHARS else text[: ARGUMENT_SUMMARY_CHARS - 1] + "…"


def _caller(ctx) -> tuple[str | None, str | None]:
    """(MCP session id, client IP) from the HTTP request; None for in-process calls."""
    request = getattr(ctx, "request", None)
    headers = getattr(request, "headers", None)
    if headers is None:
        return None, None
    peer = getattr(getattr(request, "client", None), "host", None)
    return headers.get("mcp-session-id"), client_ip(headers, peer)


def refused_result(message: str, protocol_version: str | None) -> dict:
    """An error tool result the model can read (protocol 2026-07-28 also wants resultType)."""
    result: dict = {"content": [{"type": "text", "text": message}], "isError": True}
    if (protocol_version or "") >= "2026-07-28":
        result["resultType"] = "complete"
    return result


def make_middleware(get_limiter):
    """MCP server middleware; `get_limiter` returns the current McpLimiter (swappable in tests)."""

    async def limit_and_record(ctx, call_next):
        if ctx.method != "tools/call":
            return await call_next(ctx)
        params = ctx.params or {}
        tool = str(params.get("name", "?"))[:64]
        session_id, ip = _caller(ctx)
        code = caller_code(ip)
        limiter: McpLimiter = get_limiter()
        try:
            limiter.check(session_id, ip)
        except LimitExceeded as exc:
            usage.add(tool, "refused", 0)
            logger.info("mcp refused tool=%s caller=%s reason=%s", tool, code, exc)
            return refused_result(str(exc), getattr(ctx, "protocol_version", None))
        started = time.perf_counter()
        outcome = "error"
        try:
            result = await call_next(ctx)
            is_error = result.get("isError") if isinstance(result, dict) else getattr(result, "is_error", False)
            outcome = "error" if is_error else "ok"
            return result
        finally:
            ms = int((time.perf_counter() - started) * 1000)
            usage.add(tool, outcome, ms)
            logger.info(
                "mcp call tool=%s outcome=%s ms=%d caller=%s session=%s args=%s",
                tool, outcome, ms, code, "yes" if session_id else "no", _summary(params.get("arguments")),
            )
            if usage.due():
                await anyio.to_thread.run_sync(usage.flush)

    return limit_and_record


def usage_since(db, since: date) -> list[McpUsage]:
    return list(db.execute(select(McpUsage).where(McpUsage.day >= since).order_by(McpUsage.day, McpUsage.tool)).scalars())

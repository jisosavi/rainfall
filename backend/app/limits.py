"""Traffic limits against obvious abuse, kept in memory (one web process on Railway; a restart
resets them, which is fine for this purpose).

MCP tool calls are limited per MCP session (each Claude conversation has its own), per client IP
as a backstop (much higher for Anthropic's outbound range, which all Claude users share), and
globally: above the global rate the MCP tools pause for everyone for a while, with a message
saying when to retry. The REST API has a generous per-IP limit. All numbers are settings.
"""

import ipaddress
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MINUTE = 60.0
DAY = 86_400.0


class LimitExceeded(Exception):
    """A limit was hit; the message says what and when to try again."""

    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


class _Window:
    """Counts per key in fixed windows (e.g. each clock minute)."""

    def __init__(self, seconds: float):
        self.seconds = seconds
        self.start = 0.0
        self.counts: dict[str, int] = defaultdict(int)

    def hit(self, key: str, now: float) -> int:
        start = now - (now % self.seconds)
        if start != self.start:
            self.start, self.counts = start, defaultdict(int)
        self.counts[key] += 1
        return self.counts[key]

    def retry_after(self, now: float) -> int:
        return max(1, int(self.start + self.seconds - now) + 1)


@dataclass
class McpLimits:
    session_per_minute: int = 60
    session_per_day: int = 1500
    ip_per_minute: int = 60
    trusted_ip_per_minute: int = 1000
    global_per_minute: int = 1200
    pause_minutes: int = 15
    trusted_ranges: tuple[str, ...] = ("160.79.104.0/21",)


def _utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%H:%M UTC")


class McpLimiter:
    def __init__(self, limits: McpLimits, clock=time.time):
        self.limits = limits
        self.clock = clock
        self.networks = [ipaddress.ip_network(r, strict=False) for r in limits.trusted_ranges]
        self.lock = threading.Lock()
        self.minute = _Window(MINUTE)
        self.day = _Window(DAY)
        self.paused_until = 0.0

    def trusted(self, ip: str | None) -> bool:
        try:
            address = ipaddress.ip_address(ip or "")
        except ValueError:
            return False
        return any(address in network for network in self.networks)

    def check(self, session_id: str | None, ip: str | None) -> None:
        """Count one tool call; raise LimitExceeded if it's over a limit (it then doesn't run)."""
        with self.lock:
            now = self.clock()
            if now < self.paused_until:
                raise LimitExceeded(self._pause_message(), int(self.paused_until - now) + 1)
            if self.minute.hit("global", now) > self.limits.global_per_minute:
                self.paused_until = now + self.limits.pause_minutes * MINUTE
                logger.warning(
                    "mcp: over %d calls a minute, pausing tools until %s", self.limits.global_per_minute, _utc(self.paused_until)
                )
                raise LimitExceeded(self._pause_message(), int(self.paused_until - now) + 1)
            ip_limit = self.limits.trusted_ip_per_minute if self.trusted(ip) else self.limits.ip_per_minute
            if ip and self.minute.hit(f"ip:{ip}", now) > ip_limit:
                raise LimitExceeded(
                    f"Too many requests from this address (limit {ip_limit} a minute). Try again in a minute.",
                    self.minute.retry_after(now),
                )
            if session_id:
                if self.minute.hit(f"session:{session_id}", now) > self.limits.session_per_minute:
                    raise LimitExceeded(
                        f"Too many tool calls in this session (limit {self.limits.session_per_minute} a minute). "
                        "Try again in a minute.",
                        self.minute.retry_after(now),
                    )
                if self.day.hit(f"session:{session_id}", now) > self.limits.session_per_day:
                    raise LimitExceeded(
                        f"This session has reached its daily limit of {self.limits.session_per_day} tool calls.",
                        self.day.retry_after(now),
                    )

    def _pause_message(self) -> str:
        return (
            "The Nordic weather service is paused because of unusually high traffic. "
            f"Please try again after {_utc(self.paused_until)}."
        )


class RestLimiter:
    """Per-IP limit for the REST API."""

    def __init__(self, per_minute: int, clock=time.time):
        self.per_minute = per_minute
        self.clock = clock
        self.lock = threading.Lock()
        self.minute = _Window(MINUTE)

    def check(self, ip: str | None) -> None:
        if not ip or self.per_minute <= 0:
            return
        with self.lock:
            now = self.clock()
            if self.minute.hit(ip, now) > self.per_minute:
                raise LimitExceeded(
                    f"Too many requests (limit {self.per_minute} a minute). Try again in a minute.", self.minute.retry_after(now)
                )


def client_ip(headers, fallback: str | None = None) -> str | None:
    """The caller's address as Railway's proxy saw it: X-Real-IP, else the last X-Forwarded-For
    entry (the one the proxy added; earlier entries come from the client and can be faked)."""
    headers = headers or {}
    real = (headers.get("x-real-ip") or "").strip()
    if real:
        return real
    forwarded = [part.strip() for part in (headers.get("x-forwarded-for") or "").split(",") if part.strip()]
    return forwarded[-1] if forwarded else fallback

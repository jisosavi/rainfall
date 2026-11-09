"""Log lines by level: INFO and below to stdout, WARNING and above to stderr.

Railway marks every stderr line as an error. Python's logging and uvicorn write to stderr by default, so normal
lines ("Application startup complete") showed as errors; writing everything to stdout instead would show real
errors as info. Used by the web app (app.main) and the ingest (app.ingest).
"""

from __future__ import annotations

import logging
import sys


class _Below(logging.Filter):
    def __init__(self, level: int):
        super().__init__()
        self.level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self.level


def handlers(fmt: str) -> list[logging.Handler]:
    formatter = logging.Formatter(fmt)
    out = logging.StreamHandler(sys.stdout)
    out.addFilter(_Below(logging.WARNING))
    err = logging.StreamHandler(sys.stderr)
    err.setLevel(logging.WARNING)
    for h in (out, err):
        h.setFormatter(formatter)
    return [out, err]


def configure(fmt: str, level: int = logging.INFO, uvicorn: bool = False) -> None:
    """Root logger through the split handlers (`force` replaces handlers a library may have installed); with
    `uvicorn`, its loggers write through the root too."""
    logging.basicConfig(level=level, handlers=handlers(fmt), force=True)
    if uvicorn:
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            lg = logging.getLogger(name)
            lg.handlers.clear()
            lg.propagate = True

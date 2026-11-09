"""Log levels: INFO to stdout, WARNING and above to stderr (Railway marks stderr lines as errors)."""

import logging

from app import logsetup


def test_levels_split_between_stdout_and_stderr(capsys):
    log = logging.getLogger("test.logsetup")
    log.propagate = False
    log.handlers = logsetup.handlers("%(levelname)s %(message)s")  # bound to capsys's streams
    log.setLevel(logging.INFO)
    log.info("ingest done")
    log.warning("station skipped")
    log.error("source failed")
    out, err = capsys.readouterr()
    assert "ingest done" in out and "station skipped" not in out and "source failed" not in out
    assert "station skipped" in err and "source failed" in err and "ingest done" not in err

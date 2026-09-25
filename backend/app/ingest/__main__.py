"""Run ingestion: `python -m app.ingest [--source fmi|met|smhi|all] [--start YYYY-MM-DD] [--end YYYY-MM-DD]`.

Without dates, each source backfills from INGEST_START_DATE if it has no data yet,
otherwise re-fetches its last INGEST_REFETCH_DAYS days (sources revise recent values).
MET Norway needs FROST_CLIENT_ID; with --source all it is skipped when that is unset.

`--source smhi --archive-refresh` re-loads the last SMHI_ARCHIVE_REFRESH_DAYS days of rainfall
and snow depth from SMHI's corrected archive, replacing preliminary values (run monthly).
"""

import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone

import httpx

from app.config import get_settings
from app.db.session import SessionLocal
from app.ingest import fmi, met, smhi
from app.db.models import PRECIPITATION, SNOW_DEPTH
from app.ingest.service import default_range, run_ingest

logger = logging.getLogger("app.ingest")

ALL_SOURCES = ["fmi", "met", "smhi"]
# Measurement types each source provides.
SOURCE_PARAMETERS = {source: (PRECIPITATION, SNOW_DEPTH) for source in ALL_SOURCES}


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ingest")
    parser.add_argument("--source", choices=[*ALL_SOURCES, "all"], default="all")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--archive-refresh", action="store_true", help="SMHI only: re-load recent corrected archive data")
    args = parser.parse_args()

    # stdout, not the default stderr: Railway marks everything on stderr as an error.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()

    sources = ALL_SOURCES.copy() if args.source == "all" else [args.source]
    if args.archive_refresh and sources != ["smhi"]:
        logger.error("--archive-refresh applies to --source smhi only")
        return 2
    if "met" in sources and not settings.frost_client_id:
        if args.source == "met":
            logger.error("FROST_CLIENT_ID is not set")
            return 1
        logger.warning("FROST_CLIENT_ID is not set, skipping MET Norway")
        sources.remove("met")

    failed = False
    with SessionLocal() as session:
        for source in sources:
            start, end = default_range(
                session, source, settings.ingest_start_date, settings.ingest_refetch_days,
                parameters=SOURCE_PARAMETERS[source],
            )
            if args.archive_refresh:
                today = datetime.now(timezone.utc).date()
                start = max(settings.ingest_start_date, today - timedelta(days=settings.smhi_archive_refresh_days))
            start, end = args.start or start, args.end or end
            if start > end:
                logger.info("%s: nothing to fetch (%s > %s)", source, start, end)
                continue
            logger.info("%s: ingesting %s %s..%s", source, "+".join(SOURCE_PARAMETERS[source]), start, end)
            try:
                total = _ingest(session, source, start, end, settings, args.archive_refresh)
            except Exception:
                # One failing source must not block the others.
                logger.exception("%s: ingestion failed", source)
                session.rollback()
                failed = True
                continue
            logger.info("%s: done, %d values upserted", source, total)
    return 1 if failed else 0


def _ingest(session, source: str, start: date, end: date, settings, archive_refresh: bool) -> int:
    if source == "fmi":
        with httpx.Client(timeout=120, headers={"User-Agent": met.USER_AGENT}) as client:
            return run_ingest(session, lambda a, b: fmi.fetch_daily(client, a, b), start, end, source)
    total = 0
    if source == "met":
        with met.make_client(settings.frost_client_id) as client:
            for parameter in SOURCE_PARAMETERS[source]:
                stations = met.fetch_stations(client, start, end, parameter)
                logger.info("met %s: %d stations", parameter, len(stations))
                fetch = lambda a, b, stations=stations, parameter=parameter: met.fetch_daily(client, a, b, stations, parameter)
                total += run_ingest(session, fetch, start, end, f"met {parameter}")
        return total
    # SMHI serves whole periods per station, so fetch once and store in date chunks.
    with smhi.make_client() as client:
        for parameter in SOURCE_PARAMETERS[source]:
            stations = smhi.fetch_stations(client, start, end, parameter)
            logger.info("smhi %s: %d stations", parameter, len(stations))
            series = smhi.fetch_daily(
                client, start, end, stations, use_archive=True if archive_refresh else None, parameter=parameter
            )
            total += run_ingest(session, lambda a, b, series=series: smhi.slice_series(series, a, b), start, end, f"smhi {parameter}")
    return total


if __name__ == "__main__":
    sys.exit(main())

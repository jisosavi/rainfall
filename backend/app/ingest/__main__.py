"""Run ingestion: `python -m app.ingest [--source fmi|met|all] [--start YYYY-MM-DD] [--end YYYY-MM-DD]`.

Without dates, each source backfills from INGEST_START_DATE if it has no data yet,
otherwise re-fetches its last INGEST_REFETCH_DAYS days (sources revise recent values).
MET Norway needs FROST_CLIENT_ID; with --source all it is skipped when that is unset.
"""

import argparse
import logging
import sys
from datetime import date

import httpx

from app.config import get_settings
from app.db.session import SessionLocal
from app.ingest import fmi, met
from app.ingest.service import default_range, run_ingest

logger = logging.getLogger("app.ingest")


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ingest")
    parser.add_argument("--source", choices=["fmi", "met", "all"], default="all")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    args = parser.parse_args()

    # stdout, not the default stderr: Railway marks everything on stderr as an error.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()

    sources = ["fmi", "met"] if args.source == "all" else [args.source]
    if "met" in sources and not settings.frost_client_id:
        if args.source == "met":
            logger.error("FROST_CLIENT_ID is not set")
            return 1
        logger.warning("FROST_CLIENT_ID is not set, skipping MET Norway")
        sources.remove("met")

    failed = False
    with SessionLocal() as session:
        for source in sources:
            start, end = default_range(session, source, settings.ingest_start_date, settings.ingest_refetch_days)
            start, end = args.start or start, args.end or end
            if start > end:
                logger.info("%s: nothing to fetch (%s > %s)", source, start, end)
                continue
            logger.info("%s: ingesting daily precipitation %s..%s", source, start, end)
            try:
                if source == "fmi":
                    with httpx.Client(timeout=120, headers={"User-Agent": met.USER_AGENT}) as client:
                        total = run_ingest(session, lambda a, b: fmi.fetch_daily(client, a, b), start, end, source)
                else:
                    with met.make_client(settings.frost_client_id) as client:
                        stations = met.fetch_stations(client, start, end)
                        logger.info("met: %d stations", len(stations))
                        total = run_ingest(
                            session, lambda a, b: met.fetch_daily(client, a, b, stations), start, end, source
                        )
            except Exception:
                # One failing source must not block the other.
                logger.exception("%s: ingestion failed", source)
                session.rollback()
                failed = True
                continue
            logger.info("%s: done, %d values upserted", source, total)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

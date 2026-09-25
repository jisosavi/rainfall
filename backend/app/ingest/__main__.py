"""Run FMI ingestion: `python -m app.ingest [--start YYYY-MM-DD] [--end YYYY-MM-DD]`.

Without arguments: backfills from INGEST_START_DATE on an empty DB, otherwise
re-fetches the last INGEST_REFETCH_DAYS days (FMI corrects recent values).
"""

import argparse
import logging
import sys
from datetime import date

import httpx

from app.config import get_settings
from app.db.session import SessionLocal
from app.ingest.service import default_range, run_ingest


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ingest")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()

    with SessionLocal() as session, httpx.Client(timeout=120, headers={"User-Agent": "rainfall-ingest"}) as client:
        start, end = default_range(session, settings.ingest_start_date, settings.ingest_refetch_days)
        start, end = args.start or start, args.end or end
        if start > end:
            logging.info("Nothing to fetch (%s > %s)", start, end)
            return 0
        logging.info("Ingesting FMI daily precipitation %s..%s", start, end)
        total = run_ingest(session, client, start, end)
    logging.info("Done: %d values upserted", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())

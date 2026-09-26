"""Run ingestion: `python -m app.ingest [--source fmi|met|smhi|dmi|imo|all] [--start YYYY-MM-DD] [--end YYYY-MM-DD]`.

Without dates, each source backfills from INGEST_START_DATE if it has no data yet,
otherwise re-fetches its last INGEST_REFETCH_DAYS days (sources revise recent values).
MET Norway needs FROST_CLIENT_ID; with --source all it is skipped when that is unset.

After fetching, the spatial quality check (app.qc) re-flags suspect values over the dates
the run covered; a measurement whose rules changed (app.qc.RULES_VERSION) is rechecked from
INGEST_START_DATE once. `--qc-only` runs just the check for --start..--end (default: from
INGEST_START_DATE to yesterday).

`--source smhi --archive-refresh` re-loads the last SMHI_ARCHIVE_REFRESH_DAYS days of rainfall,
snow depth and temperature from SMHI's corrected archive, replacing preliminary values (run monthly).
"""

import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone

import httpx

from app.config import get_settings
from app.db.session import SessionLocal
from app.ingest import dmi, fmi, imo, met, smhi
from app.db.models import PARAMETERS, PRECIPITATION, SNOW_DEPTH, TEMPERATURES
from app.qc import confirm_with_hourly, flag_spatial_outliers, mark_checked, stale_parameters
from app.ingest.service import default_range, run_ingest

logger = logging.getLogger("app.ingest")

ALL_SOURCES = ["fmi", "met", "smhi", "dmi", "imo"]
# Measurement types each source provides.
SOURCE_PARAMETERS = {source: (PRECIPITATION, SNOW_DEPTH, *TEMPERATURES) for source in ALL_SOURCES}


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ingest")
    parser.add_argument("--source", choices=[*ALL_SOURCES, "all"], default="all")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--archive-refresh", action="store_true", help="SMHI only: re-load recent corrected archive data")
    parser.add_argument("--qc-only", action="store_true", help="only run the spatial quality check")
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

    if args.qc_only:
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        with SessionLocal() as session:
            qc_start, qc_end = args.start or settings.ingest_start_date, args.end or yesterday
            flag_spatial_outliers(session, qc_start, qc_end)
            _confirm_hourly(session, qc_start, qc_end, settings)
            if qc_start <= settings.ingest_start_date and qc_end >= yesterday:
                mark_checked(session, list(PARAMETERS))
        return 0

    failed = False
    covered: list[tuple[date, date]] = []
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
            covered.append((start, end))

        if covered:
            # Neighbours come from all sources, so check the whole span this run touched.
            try:
                qc_start, qc_end = min(s for s, _ in covered), max(e for _, e in covered)
                stale = stale_parameters(session)
                current = tuple(p for p in PARAMETERS if p not in stale)
                if current:
                    flag_spatial_outliers(session, qc_start, qc_end, current)
                if stale:
                    logger.info("qc: rules changed for %s, rechecking from %s", ", ".join(stale), settings.ingest_start_date)
                    flag_spatial_outliers(session, settings.ingest_start_date, qc_end, tuple(stale))
                    mark_checked(session, stale)
                confirm_start = settings.ingest_start_date if PRECIPITATION in stale else qc_start
                _confirm_hourly(session, confirm_start, qc_end, settings)
            except Exception:
                logger.exception("qc: spatial check failed")
                session.rollback()
                failed = True
    return 1 if failed else 0


def _confirm_hourly(session, start: date, end: date, settings) -> None:
    """Check suspect rainfall against each station's hourly readings (few requests per run)."""
    smhi_cache: dict = {}
    with (
        httpx.Client(timeout=120, headers={"User-Agent": met.USER_AGENT}) as fmi_client,
        smhi.make_client() as smhi_client,
        dmi.make_client() as dmi_client,
        met.make_client(settings.frost_client_id or "") as met_client,
    ):
        def fetch(source: str, station_id: str, day: date) -> list[float]:
            if source == "fmi":
                return fmi.fetch_hourly_precipitation(fmi_client, station_id, day)
            if source == "met":
                return met.fetch_hourly_precipitation(met_client, station_id, day) if settings.frost_client_id else []
            if source == "dmi":
                return dmi.fetch_hourly_precipitation(dmi_client, station_id, day)
            if source == "imo":
                return []  # IMO publishes no hourly rainfall
            return smhi.fetch_hourly_precipitation(smhi_client, station_id, day, cache=smhi_cache)

        confirm_with_hourly(session, start, end, fetch)


def _ingest(session, source: str, start: date, end: date, settings, archive_refresh: bool) -> int:
    if source == "fmi":
        with httpx.Client(timeout=120, headers={"User-Agent": met.USER_AGENT}) as client:
            # Station heights (for the neighbour check's altitude window); optional.
            try:
                elevations = fmi.fetch_elevations(client)
                logger.info("fmi: %d station heights", len(elevations))
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("fmi: station heights unavailable (%s)", exc)
                elevations = {}
            # Daily values (rainfall, snow, min/max), then the 00–24 UTC mean from hourly data.
            fetch_daily = lambda a, b: fmi.with_elevations(fmi.fetch_daily(client, a, b), elevations)
            total = run_ingest(session, fetch_daily, start, end, source)
            fetch_mean = lambda a, b: fmi.with_elevations(fmi.fetch_daily_mean_temperature(client, a, b), elevations)
            return total + run_ingest(session, fetch_mean, start, end, "fmi temp_mean")
    total = 0
    if source == "met":
        with met.make_client(settings.frost_client_id) as client:
            for parameter in SOURCE_PARAMETERS[source]:
                stations = met.fetch_stations(client, start, end, parameter)
                logger.info("met %s: %d stations", parameter, len(stations))
                fetch = lambda a, b, stations=stations, parameter=parameter: met.fetch_daily(client, a, b, stations, parameter)
                total += run_ingest(session, fetch, start, end, f"met {parameter}")
        return total
    if source == "imo":
        with imo.make_client() as client:
            stations = imo.fetch_stations(client)
            logger.info("imo: %d stations", len(stations))
            for parameter in SOURCE_PARAMETERS[source]:
                fetch = lambda a, b, parameter=parameter: imo.fetch_daily(client, a, b, stations, parameter)
                total += run_ingest(session, fetch, start, end, f"imo {parameter}")
        return total
    if source == "dmi":
        with dmi.make_client() as client:
            for parameter in SOURCE_PARAMETERS[source]:
                stations = dmi.fetch_stations(client, start, end, parameter)
                logger.info("dmi %s: %d stations", parameter, len(stations))
                fetch = lambda a, b, stations=stations, parameter=parameter: dmi.fetch_daily(client, a, b, stations, parameter)
                total += run_ingest(session, fetch, start, end, f"dmi {parameter}")
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

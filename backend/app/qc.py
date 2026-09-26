"""Our own quality control on stored values, run after each ingestion.

Spatial "buddy check": an unusually high value is compared with the same day's values at
nearby stations (any source, so across borders too). If it is far above even the highest
neighbour, it is flagged `suspect_spatial`. Flagged values stay visible (they may be real)
but are marked in the UI and left out of rankings.

Comparing with the *highest* neighbour, not the average, protects genuine local downpours:
a flag needs every neighbour to be much lower. Without enough neighbours nothing is judged.
For snow depth, altitude matters more than distance (a mountain station has far more snow
than a valley 20 km away), so only neighbours within MAX_ELEVATION_DIFF are compared when
both elevations are known (MET Norway and SMHI give them; FMI's daily data doesn't).
Temperature is checked both ways: a value far from the median of its neighbours (within
50 km and 300 m of altitude) is suspect, whether too warm or too cold. The limits are wide,
minimum temperatures widest, because frost hollows are real. In cold weather (neighbour
median below 0 °C) temperature inversions make valleys 15–20 °C colder than slopes a few
kilometres away (Kilpisjärvi, Kittilä, Bjorli, Folldal in 2025–26), so the limit is then
INVERSION_DEVIATION for all three.
Flagged rainfall is then checked against the station's own hourly readings: if they add up
to the daily value, the storm was real and the flag becomes `confirmed_hourly` (ranked as
normal). Stations without hourly data (mostly manual) keep the flag.
Hard limits for impossible values are separate (app.ingest.common.PLAUSIBLE_RANGE).
"""

import logging
import math
import statistics
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.db.models import PARAMETERS, DailyValue, QcState, Station
from app.ingest.common import date_chunks

logger = logging.getLogger(__name__)

SUSPECT_SPATIAL = "suspect_spatial"
CONFIRMED_HOURLY = "confirmed_hourly"

# (source, source_station_id, day) -> the station's hourly rainfall values for our day D.
HourlyFetcher = Callable[[str, str, date], list[float]]


@dataclass(frozen=True)
class Rule:
    min_value: float  # only values at least this high are checked
    radius_km: float
    min_neighbours: int
    factor: float  # suspect if value > factor * highest neighbour + margin
    margin: float
    max_elevation_diff: float | None = None  # metres; None = compare regardless of altitude
    max_deviation: float | None = None  # two-sided: suspect if |value - neighbour median| > this
    inversion_deviation: float | None = None  # two-sided limit when the neighbour median is below 0


INVERSION_DEVIATION = 20.0  # °C


RULES = {
    "precipitation": Rule(min_value=30, radius_km=50, min_neighbours=3, factor=3, margin=20),  # mm
    "snow_depth": Rule(min_value=50, radius_km=30, min_neighbours=3, factor=3, margin=50, max_elevation_diff=300),  # cm
    # °C; min_value/factor/margin are unused for two-sided rules.
    **{
        parameter: Rule(
            0, radius_km=50, min_neighbours=3, factor=0, margin=0, max_elevation_diff=300,
            max_deviation=deviation, inversion_deviation=INVERSION_DEVIATION,
        )
        for parameter, deviation in (("temp_mean", 10), ("temp_min", 15), ("temp_max", 10))
    },
}
# Bump a measurement's version when its rule changes: the next ingestion run then rechecks
# its whole history once (tracked in the qc_state table), not just the re-fetched days.
RULES_VERSION = {
    "precipitation": 1,
    "snow_depth": 1,
    "temp_mean": 2,  # 2: inversion allowance, FMI station heights
    "temp_min": 2,
    "temp_max": 2,
}

Position = tuple[float, float, float | None]  # lat, lon, elevation_m


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _similar_altitude(a: float | None, b: float | None, rule: Rule) -> bool:
    return rule.max_elevation_diff is None or a is None or b is None or abs(a - b) <= rule.max_elevation_diff


def find_suspects(day_values: dict[UUID, float], positions: dict[UUID, Position], rule: Rule) -> list[UUID]:
    """Stations whose value on one day is far above all their neighbours' values (or, for a
    two-sided rule, far from their median)."""
    two_sided = rule.max_deviation is not None
    suspects = []
    lat_span = rule.radius_km / 111.0
    for station_id, value in day_values.items():
        if (not two_sided and value < rule.min_value) or station_id not in positions:
            continue
        lat, lon, elevation = positions[station_id]
        lon_span = lat_span / max(math.cos(math.radians(lat)), 0.1)
        neighbours = [
            other_value
            for other_id, other_value in day_values.items()
            if other_id != station_id
            and other_id in positions
            and abs(positions[other_id][0] - lat) <= lat_span
            and abs(positions[other_id][1] - lon) <= lon_span
            and _similar_altitude(elevation, positions[other_id][2], rule)
            and _km(lat, lon, positions[other_id][0], positions[other_id][1]) <= rule.radius_km
        ]
        if len(neighbours) < rule.min_neighbours:
            continue
        if two_sided:
            median = statistics.median(neighbours)
            limit = rule.inversion_deviation if rule.inversion_deviation is not None and median < 0 else rule.max_deviation
            if abs(value - median) > limit:
                suspects.append(station_id)
        elif value > rule.factor * max(neighbours) + rule.margin:
            suspects.append(station_id)
    return suspects


def hourly_confirms(daily: float, hourly: list[float]) -> bool:
    """The hours add up to the daily value (within 5 mm or 20%). Some stations only report
    hours with rain, so the number of hours isn't required, only that the sum matches."""
    return bool(hourly) and abs(sum(hourly) - daily) <= max(5.0, 0.2 * daily)


def confirm_with_hourly(session: Session, start: date, end: date, fetch_hourly: HourlyFetcher) -> int:
    """Re-check suspect rainfall in start..end against hourly readings. Returns number confirmed."""
    rows = session.execute(
        select(DailyValue, Station.source, Station.source_station_id)
        .join(Station)
        .where(
            DailyValue.parameter == "precipitation",
            DailyValue.flag == SUSPECT_SPATIAL,
            DailyValue.date.between(start, end),
        )
    ).all()
    confirmed = 0
    for row, source, source_station_id in rows:
        try:
            hourly = fetch_hourly(source, source_station_id, row.date)
        except Exception as exc:  # a failed lookup leaves the flag in place
            logger.warning("qc hourly %s %s %s failed: %s", source, source_station_id, row.date, exc)
            continue
        if hourly_confirms(row.value, hourly):
            row.flag = CONFIRMED_HOURLY
            confirmed += 1
    session.commit()
    logger.info("qc precipitation %s..%s: %d of %d suspect values confirmed by hourly readings", start, end, confirmed, len(rows))
    return confirmed


def flag_spatial_outliers(
    session: Session, start: date, end: date, parameters: tuple[str, ...] = PARAMETERS
) -> dict[str, int]:
    """Recompute `suspect_spatial` flags for start..end. Returns the number flagged per parameter."""
    positions: dict[UUID, Position] = {
        sid: (lat, lon, elevation)
        for sid, lat, lon, elevation in session.execute(select(Station.id, Station.lat, Station.lon, Station.elevation_m))
    }
    counts: dict[str, int] = {}
    for parameter in parameters:
        rule = RULES[parameter]
        flagged = 0
        for chunk_start, chunk_end in date_chunks(start, end):
            window = and_(
                DailyValue.parameter == parameter, DailyValue.date.between(chunk_start, chunk_end)
            )
            session.execute(update(DailyValue).where(window, DailyValue.flag == SUSPECT_SPATIAL).values(flag=None))

            by_day: dict[date, dict[UUID, float]] = defaultdict(dict)
            confirmed: set[tuple[UUID, date]] = set()
            rows = session.execute(
                select(DailyValue.station_id, DailyValue.date, DailyValue.value, DailyValue.flag).where(
                    window, DailyValue.has_data.is_(True)
                )
            )
            for station_id, day, value, flag in rows:
                by_day[day][station_id] = value
                if flag == CONFIRMED_HOURLY:
                    confirmed.add((station_id, day))

            for day, day_values in by_day.items():
                for station_id in find_suspects(day_values, positions, rule):
                    if (station_id, day) in confirmed:  # already verified as real
                        continue
                    session.execute(
                        update(DailyValue)
                        .where(
                            DailyValue.station_id == station_id,
                            DailyValue.parameter == parameter,
                            DailyValue.date == day,
                        )
                        .values(flag=SUSPECT_SPATIAL)
                    )
                    flagged += 1
            session.commit()
        counts[parameter] = flagged
        logger.info("qc %s %s..%s: %d values flagged suspect_spatial", parameter, start, end, flagged)
    return counts


def stale_parameters(session: Session) -> list[str]:
    """Measurements whose whole history was last checked with older rules (never = version 1)."""
    stored = dict(session.execute(select(QcState.parameter, QcState.rules_version)).all())
    return [p for p in PARAMETERS if stored.get(p, 1) < RULES_VERSION[p]]


def mark_checked(session: Session, parameters: list[str]) -> None:
    for parameter in parameters:
        session.merge(QcState(parameter=parameter, rules_version=RULES_VERSION[parameter], checked_at=datetime.now(timezone.utc)))
    session.commit()

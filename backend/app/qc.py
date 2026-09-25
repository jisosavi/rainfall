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
Hard limits for impossible values are separate (app.ingest.common.PLAUSIBLE_MAX).
"""

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.db.models import PARAMETERS, DailyValue, Station
from app.ingest.common import date_chunks

logger = logging.getLogger(__name__)

SUSPECT_SPATIAL = "suspect_spatial"


@dataclass(frozen=True)
class Rule:
    min_value: float  # only values at least this high are checked
    radius_km: float
    min_neighbours: int
    factor: float  # suspect if value > factor * highest neighbour + margin
    margin: float
    max_elevation_diff: float | None = None  # metres; None = compare regardless of altitude


RULES = {
    "precipitation": Rule(min_value=30, radius_km=50, min_neighbours=3, factor=3, margin=20),  # mm
    "snow_depth": Rule(min_value=50, radius_km=30, min_neighbours=3, factor=3, margin=50, max_elevation_diff=300),  # cm
}

Position = tuple[float, float, float | None]  # lat, lon, elevation_m


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _similar_altitude(a: float | None, b: float | None, rule: Rule) -> bool:
    return rule.max_elevation_diff is None or a is None or b is None or abs(a - b) <= rule.max_elevation_diff


def find_suspects(day_values: dict[UUID, float], positions: dict[UUID, Position], rule: Rule) -> list[UUID]:
    """Stations whose value on one day is far above all their neighbours' values."""
    suspects = []
    lat_span = rule.radius_km / 111.0
    for station_id, value in day_values.items():
        if value < rule.min_value or station_id not in positions:
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
        if len(neighbours) >= rule.min_neighbours and value > rule.factor * max(neighbours) + rule.margin:
            suspects.append(station_id)
    return suspects


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
            rows = session.execute(
                select(DailyValue.station_id, DailyValue.date, DailyValue.value).where(window, DailyValue.has_data.is_(True))
            )
            for station_id, day, value in rows:
                by_day[day][station_id] = value

            for day, day_values in by_day.items():
                for station_id in find_suspects(day_values, positions, rule):
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

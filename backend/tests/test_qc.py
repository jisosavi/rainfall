from datetime import date
from uuid import uuid4

from sqlalchemy import select

from app.db.models import DailyValue, Station
from app.qc import RULES, SUSPECT_SPATIAL, find_suspects, flag_spatial_outliers

RAIN, SNOW = RULES["precipitation"], RULES["snow_depth"]


def ids(n):
    return [uuid4() for _ in range(n)]


def test_value_far_above_all_neighbours_is_suspect():
    a, b, c, d = ids(4)
    positions = {a: (61.0, 25.0, None), b: (61.1, 25.0, None), c: (61.0, 25.2, None), d: (60.9, 25.1, None)}
    # 3 * 10 + 20 = 50: 76 mm is suspect, 45 mm is not.
    assert find_suspects({a: 76.0, b: 10.0, c: 8.0, d: 2.0}, positions, RAIN) == [a]
    assert find_suspects({a: 45.0, b: 10.0, c: 8.0, d: 2.0}, positions, RAIN) == []


def test_local_downpour_with_one_wet_neighbour_is_kept():
    a, b, c, d = ids(4)
    positions = {a: (62.0, 24.0, None), b: (62.1, 24.0, None), c: (62.0, 24.2, None), d: (61.9, 24.1, None)}
    # Like Multia 114 mm: one neighbour also got heavy rain, so 114 < 3 * 40 + 20.
    assert find_suspects({a: 114.0, b: 40.0, c: 5.0, d: 3.0}, positions, RAIN) == []


def test_too_few_neighbours_or_far_away_is_not_judged():
    a, b, c = ids(3)
    near = {a: (61.0, 25.0, None), b: (61.1, 25.0, None), c: (61.0, 25.2, None)}
    assert find_suspects({a: 90.0, b: 1.0, c: 1.0}, near, RAIN) == []  # only 2 neighbours
    far = {a: (61.0, 25.0, None), b: (62.0, 25.0, None), c: (63.0, 25.0, None)}
    assert find_suspects({a: 90.0, b: 1.0, c: 1.0}, far, RAIN) == []


def test_snow_compares_only_similar_altitude():
    mountain, v1, v2, v3 = ids(4)
    positions = {mountain: (61.5, 7.9, 1413.0), v1: (61.6, 7.9, 200.0), v2: (61.5, 8.1, 300.0), v3: (61.4, 7.8, 150.0)}
    # A mountain station with 180 cm above valley stations with 20 cm: not comparable.
    assert find_suspects({mountain: 180.0, v1: 20.0, v2: 15.0, v3: 10.0}, positions, SNOW) == []
    positions[mountain] = (61.5, 7.9, 250.0)  # same valley altitude: now clearly suspect
    assert find_suspects({mountain: 180.0, v1: 20.0, v2: 15.0, v3: 10.0}, positions, SNOW) == [mountain]


def test_flags_are_recomputed(db):
    stations = [Station(source="fmi", source_station_id=str(i), name=f"S{i}", lat=61.0 + i * 0.05, lon=25.0) for i in range(4)]
    db.add_all(stations)
    db.flush()
    values = [76.0, 10.0, 8.0, 2.0]
    rows = [DailyValue(station_id=s.id, date=date(2025, 7, 26), value=v, has_data=True) for s, v in zip(stations, values)]
    db.add_all(rows)
    db.commit()

    assert flag_spatial_outliers(db, date(2025, 7, 1), date(2025, 7, 31), ("precipitation",)) == {"precipitation": 1}
    flagged = db.scalars(select(DailyValue).where(DailyValue.flag == SUSPECT_SPATIAL)).all()
    assert [r.value for r in flagged] == [76.0]

    rows[1].value = 40.0  # a neighbour turns out wet too: the flag is cleared on the next run
    db.commit()
    assert flag_spatial_outliers(db, date(2025, 7, 1), date(2025, 7, 31), ("precipitation",)) == {"precipitation": 0}
    assert db.scalars(select(DailyValue).where(DailyValue.flag == SUSPECT_SPATIAL)).all() == []

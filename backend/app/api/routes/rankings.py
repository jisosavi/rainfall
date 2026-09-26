"""Top N rankings: GET /api/rankings (logic in app.services.rankings)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.station import Parameter
from app.services.rankings import Order, Period, RankingsResponse, period_range, rankings  # noqa: F401 (period_range re-exported)

router = APIRouter(prefix="/api", tags=["rankings"])


@router.get("/rankings", response_model=RankingsResponse)
def get_rankings(
    period: Period = Query(..., description="Rainfall: week, month, year, last30. Snow depth: now, winter_max, winter_days. Temperature: now, week, month, year, last30."),
    date_value: date = Query(..., alias="date", description="Last day of the period."),
    parameter: Parameter = Query("precipitation"),
    country: str | None = Query(None, description="fi, no, se, dk, gl, fo, is or ee; default all."),
    limit: int = Query(15, ge=1, le=100),
    min_coverage: float = Query(0.9, ge=0, le=1, description="Share of the period's days a station needs data on."),
    order: Order = Query("warmest", description="Temperature only: warmest or coldest first."),
    db: Session = Depends(get_db),
):
    return rankings(
        db, period=period, date_value=date_value, parameter=parameter, country=country,
        limit=limit, min_coverage=min_coverage, order=order,
    )

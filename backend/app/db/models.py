from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Station(Base):
    __tablename__ = "stations"

    __table_args__ = (UniqueConstraint("source", "source_station_id", name="uq_stations_source_station"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    # Data source: "fmi" (Finland), "met" (MET Norway), "smhi" (Sweden) or "dmi" (Denmark,
    # Greenland, Faroe Islands).
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="fmi", server_default="fmi")
    # The source's own station id: FMI fmisid (e.g. "100971") or Frost id (e.g. "SN18700").
    source_station_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    lat: Mapped[float] = mapped_column(Double, nullable=False)
    lon: Mapped[float] = mapped_column(Double, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="FI", server_default="FI")
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Organisation running the station, e.g. "SMHI" or "VA Syd", when the source provides it.
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Metres above sea level, when the source provides it (MET Norway, SMHI; not FMI's daily data).
    elevation_m: Mapped[float | None] = mapped_column(Double, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    values: Mapped[list["DailyValue"]] = relationship(
        back_populates="station", passive_deletes=True
    )


# Measurement types stored in daily_values.
PRECIPITATION = "precipitation"  # 24 h total, mm, 06 UTC on D to 06 UTC on D+1
SNOW_DEPTH = "snow_depth"  # reading at 06 UTC on D, cm
PARAMETERS = (PRECIPITATION, SNOW_DEPTH)
UNITS = {PRECIPITATION: "mm", SNOW_DEPTH: "cm"}


class DailyValue(Base):
    """One station, one date, one measurement type."""

    __tablename__ = "daily_values"
    __table_args__ = (
        # Also serves as the station_id index: station_id is the leading column.
        UniqueConstraint("station_id", "parameter", "date", name="uq_daily_values_station_parameter_date"),
        Index("ix_daily_values_parameter_date", "parameter", "date"),
        CheckConstraint("value IS NULL OR value >= 0", name="ck_daily_values_non_negative"),
        CheckConstraint(
            "(has_data AND value IS NOT NULL) OR (NOT has_data AND value IS NULL)",
            name="ck_daily_values_has_data_matches_value",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False
    )
    parameter: Mapped[str] = mapped_column(String(32), nullable=False, default=PRECIPITATION, server_default=PRECIPITATION)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # In the parameter's unit (see UNITS).
    value: Mapped[float | None] = mapped_column(Double, nullable=True)
    has_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Original source value/flag, e.g. FMI's "-1" for "no precipitation" or "no snow cover".
    raw_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Our own quality flag, e.g. "suspect_spatial" (far above all nearby stations that day).
    # Flagged values stay visible but are marked, and left out of rankings.
    flag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    station: Mapped[Station] = relationship(back_populates="values")

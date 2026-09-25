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
    # Data source: "fmi" (Finland) or "met" (MET Norway).
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="fmi", server_default="fmi")
    # The source's own station id: FMI fmisid (e.g. "100971") or Frost id (e.g. "SN18700").
    source_station_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    lat: Mapped[float] = mapped_column(Double, nullable=False)
    lon: Mapped[float] = mapped_column(Double, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="FI", server_default="FI")
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    precipitation_rows: Mapped[list["DailyPrecipitation"]] = relationship(
        back_populates="station", passive_deletes=True
    )


class DailyPrecipitation(Base):
    __tablename__ = "daily_precipitation"
    __table_args__ = (
        # Also serves as the station_id index: station_id is the leading column.
        UniqueConstraint("station_id", "date", name="uq_daily_precipitation_station_date"),
        Index("ix_daily_precipitation_date", "date"),
        CheckConstraint(
            "precipitation_mm IS NULL OR precipitation_mm >= 0",
            name="ck_daily_precipitation_non_negative",
        ),
        CheckConstraint(
            "(has_data AND precipitation_mm IS NOT NULL) OR (NOT has_data AND precipitation_mm IS NULL)",
            name="ck_daily_precipitation_has_data_matches_value",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    precipitation_mm: Mapped[float | None] = mapped_column(Double, nullable=True)
    has_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Original source value/flag, e.g. FMI's "-1" for "no precipitation", kept for auditing.
    raw_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    station: Mapped[Station] = relationship(back_populates="precipitation_rows")

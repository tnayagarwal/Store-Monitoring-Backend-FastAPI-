from __future__ import annotations

from datetime import datetime, time
from sqlalchemy import String, Integer, DateTime, Time, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String, index=True)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    status: Mapped[str] = mapped_column(Enum("active", "inactive", name="status_enum"), index=True)

    __table_args__ = (
        UniqueConstraint("store_id", "timestamp_utc", name="uq_store_timestamp"),
    )


class BusinessHour(Base):
    __tablename__ = "business_hours"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, index=True)  # 0=Monday ... 6=Sunday
    start_time_local: Mapped[time] = mapped_column(Time(timezone=False))
    end_time_local: Mapped[time] = mapped_column(Time(timezone=False))

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "day_of_week",
            "start_time_local",
            "end_time_local",
            name="uq_business_hour_unique_span",
        ),
    )


class StoreTimezone(Base):
    __tablename__ = "store_timezones"

    store_id: Mapped[str] = mapped_column(String, primary_key=True)
    timezone_str: Mapped[str] = mapped_column(String)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)



"""Canonical SQLAlchemy models for fitness data.

These models are currently not wired into runtime ingestion yet,
but provide the target schema in ORM form for incremental adoption.
"""
from sqlalchemy import JSON, BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawEvent(Base):
    __tablename__ = "raw_event"
    __table_args__ = (UniqueConstraint("source", "source_event_type", "payload_sha256"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_event_type: Mapped[str] = mapped_column(String, nullable=False)
    source_event_id: Mapped[str | None] = mapped_column(String)
    event_ts: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    event_date: Mapped[str | None] = mapped_column(Date)
    payload_sha256: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    ingested_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Activity(Base):
    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    canonical_uid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    start_ts: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    end_ts: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    activity_type: Mapped[str | None] = mapped_column(String)
    calories_out: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    steps: Mapped[int | None] = mapped_column(Integer)
    dedupe_key: Mapped[str | None] = mapped_column(String)


class ActivitySourceLink(Base):
    __tablename__ = "activity_source_link"
    __table_args__ = (UniqueConstraint("source", "source_activity_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activity.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_activity_id: Mapped[str] = mapped_column(String, nullable=False)
    raw_event_id: Mapped[int | None] = mapped_column(ForeignKey("raw_event.id", ondelete="SET NULL"))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)


class NutritionEntry(Base):
    __tablename__ = "nutrition_entry"
    __table_args__ = (UniqueConstraint("source", "source_entry_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_entry_id: Mapped[str] = mapped_column(String, nullable=False)
    consumed_ts: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    entry_date: Mapped[str] = mapped_column(Date, nullable=False)
    meal_name: Mapped[str | None] = mapped_column(String)
    food_name: Mapped[str | None] = mapped_column(String)
    calories: Mapped[int | None] = mapped_column(Integer)
    protein_g: Mapped[float | None] = mapped_column(Numeric(10, 2))
    carbs_g: Mapped[float | None] = mapped_column(Numeric(10, 2))
    fat_g: Mapped[float | None] = mapped_column(Numeric(10, 2))
    raw_event_id: Mapped[int | None] = mapped_column(ForeignKey("raw_event.id", ondelete="SET NULL"))


class ExportGoogleHealthActivity(Base):
    __tablename__ = "export_google_health_activity"
    __table_args__ = (UniqueConstraint("activity_id", "export_hash"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activity.id", ondelete="CASCADE"), nullable=False)
    export_hash: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    external_id: Mapped[str | None] = mapped_column(String)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_attempted_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class ExportGoogleHealthNutrition(Base):
    __tablename__ = "export_google_health_nutrition"
    __table_args__ = (UniqueConstraint("nutrition_entry_id", "export_hash"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nutrition_entry_id: Mapped[int] = mapped_column(ForeignKey("nutrition_entry.id", ondelete="CASCADE"), nullable=False)
    export_hash: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    external_id: Mapped[str | None] = mapped_column(String)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_attempted_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

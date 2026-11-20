from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Chain(Base):
    __tablename__ = "chains"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    native_symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    consensus: Mapped[str] = mapped_column(String(8), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DataSource(Base):
    __tablename__ = "data_sources"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    license_note: Mapped[str] = mapped_column(Text, nullable=False)
    attribution_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False, default="1d")
    description: Mapped[str] = mapped_column(Text, nullable=False)


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        Index(
            "ix_observations_chain_metric_date",
            "chain_code",
            "metric_code",
            "obs_date",
        ),
    )

    chain_code: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("chains.code", ondelete="CASCADE"),
        primary_key=True,
    )
    metric_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("metric_definitions.code", ondelete="CASCADE"),
        primary_key=True,
    )
    source_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("data_sources.code", ondelete="CASCADE"),
        primary_key=True,
    )
    obs_date: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(38, 12), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class SeriesCoverage(Base):
    __tablename__ = "series_coverage"

    chain_code: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("chains.code", ondelete="CASCADE"),
        primary_key=True,
    )
    metric_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("metric_definitions.code", ondelete="CASCADE"),
        primary_key=True,
    )
    source_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("data_sources.code", ondelete="CASCADE"),
        primary_key=True,
    )
    first_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    points: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    missing_days: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="never_run")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','ok','partial','error','failed','rate_limited')",
            name="ck_ingestion_runs_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    job: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rows_upserted: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


class RpcProbe(Base):
    __tablename__ = "rpc_probes"
    __table_args__ = (
        Index(
            "ix_rpc_probes_chain_provider_checked_desc",
            "chain_id",
            "provider_label",
            text("checked_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    chain_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("chains.code", ondelete="CASCADE"),
        nullable=False,
    )
    provider_label: Mapped[str] = mapped_column(String(64), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_height: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    block_age_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ComputedFeature(Base):
    __tablename__ = "features"
    __table_args__ = (Index("ix_features_chain_as_of_date", "chain_id", "as_of_date"),)

    chain_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("chains.code", ondelete="CASCADE"),
        primary_key=True,
    )
    feature: Mapped[str] = mapped_column(Text, primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(38, 12), nullable=False)
    n_obs: Mapped[int] = mapped_column(Integer, nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    source_metric: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)

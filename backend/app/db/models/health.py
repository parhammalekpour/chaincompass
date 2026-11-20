from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HealthScore(Base):
    __tablename__ = "health_scores"
    __table_args__ = (
        Index("ix_health_scores_chain_as_of_date", "chain_id", "as_of_date"),
    )

    chain_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("chains.code", ondelete="CASCADE"),
        primary_key=True,
    )
    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)
    version: Mapped[str] = mapped_column(String(16), primary_key=True)
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    coverage: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    confidence_label: Mapped[str] = mapped_column(String(16), nullable=False)
    pillars: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    components: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)


class MarketRegime(Base):
    __tablename__ = "regimes"
    __table_args__ = (
        CheckConstraint(
            "regime IN ('stress','uptrend','downtrend','range')",
            name="ck_regimes_regime",
        ),
        Index("ix_regimes_chain_as_of_date", "chain_id", "as_of_date"),
    )

    chain_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("chains.code", ondelete="CASCADE"),
        primary_key=True,
    )
    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)
    version: Mapped[str] = mapped_column(String(16), primary_key=True)
    regime: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_regime: Mapped[str] = mapped_column(String(16), nullable=False)
    vol_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    days_in_regime: Mapped[int] = mapped_column(Integer, nullable=False)


class RiskFlag(Base):
    __tablename__ = "risk_flags"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info','medium','high')",
            name="ck_risk_flags_severity",
        ),
        Index("ix_risk_flags_chain_as_of_date", "chain_id", "as_of_date"),
    )

    chain_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("chains.code", ondelete="CASCADE"),
        primary_key=True,
    )
    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)
    flag: Mapped[str] = mapped_column(String(32), primary_key=True)
    version: Mapped[str] = mapped_column(String(16), primary_key=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(38, 12), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(38, 12), nullable=False)

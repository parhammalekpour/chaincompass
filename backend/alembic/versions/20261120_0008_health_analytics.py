"""Add point-in-time Health Score, regime, and risk flag tables.

Revision ID: 20261120_0008
Revises: 20261120_0007
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261120_0008"
down_revision: str | None = "20261120_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "health_scores",
        sa.Column("chain_id", sa.String(length=16), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("coverage", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("confidence_label", sa.String(length=16), nullable=False),
        sa.Column("pillars", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "components",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chain_id", "as_of_date", "version"),
    )
    op.create_index(
        "ix_health_scores_chain_as_of_date",
        "health_scores",
        ["chain_id", "as_of_date"],
    )

    op.create_table(
        "regimes",
        sa.Column("chain_id", sa.String(length=16), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("regime", sa.String(length=16), nullable=False),
        sa.Column("raw_regime", sa.String(length=16), nullable=False),
        sa.Column("vol_state", sa.String(length=16), nullable=True),
        sa.Column("days_in_regime", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "regime IN ('stress','uptrend','downtrend','range')",
            name="ck_regimes_regime",
        ),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chain_id", "as_of_date", "version"),
    )
    op.create_index(
        "ix_regimes_chain_as_of_date",
        "regimes",
        ["chain_id", "as_of_date"],
    )

    op.create_table(
        "risk_flags",
        sa.Column("chain_id", sa.String(length=16), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("flag", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Numeric(precision=38, scale=12), nullable=False),
        sa.Column("threshold", sa.Numeric(precision=38, scale=12), nullable=False),
        sa.CheckConstraint(
            "severity IN ('info','medium','high')",
            name="ck_risk_flags_severity",
        ),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chain_id", "as_of_date", "flag", "version"),
    )
    op.create_index(
        "ix_risk_flags_chain_as_of_date",
        "risk_flags",
        ["chain_id", "as_of_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_risk_flags_chain_as_of_date", table_name="risk_flags")
    op.drop_table("risk_flags")
    op.drop_index("ix_regimes_chain_as_of_date", table_name="regimes")
    op.drop_table("regimes")
    op.drop_index("ix_health_scores_chain_as_of_date", table_name="health_scores")
    op.drop_table("health_scores")

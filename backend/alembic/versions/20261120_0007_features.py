"""Add materialized point-in-time analytics features.

Revision ID: 20261120_0007
Revises: 20261120_0006
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261120_0007"
down_revision: str | None = "20261120_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "features",
        sa.Column("chain_id", sa.String(length=16), nullable=False),
        sa.Column("feature", sa.Text(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(precision=38, scale=12), nullable=False),
        sa.Column("n_obs", sa.Integer(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("source_metric", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chain_id"],
            ["chains.code"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chain_id", "feature", "as_of_date"),
    )
    op.create_index(
        "ix_features_chain_as_of_date",
        "features",
        ["chain_id", "as_of_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_features_chain_as_of_date", table_name="features")
    op.drop_table("features")

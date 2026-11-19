"""Add ingestion data model.

Revision ID: 20261119_0004
Revises: 20261111_0003
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261119_0004"
down_revision: str | None = "20261111_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chains",
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("native_symbol", sa.String(16), nullable=False),
        sa.Column("consensus", sa.String(8), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("consensus IN ('pow','pos')", name="ck_chains_consensus"),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "data_sources",
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=False),
        sa.Column("attribution_required", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "metric_definitions",
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("frequency", sa.String(16), nullable=False, server_default="1d"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "observations",
        sa.Column("chain_code", sa.String(16), nullable=False),
        sa.Column("metric_code", sa.String(64), nullable=False),
        sa.Column("source_code", sa.String(64), nullable=False),
        sa.Column("obs_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(38, 12), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chain_code"], ["chains.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["metric_code"], ["metric_definitions.code"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_code"], ["data_sources.code"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("chain_code", "metric_code", "source_code", "obs_date"),
        sa.UniqueConstraint(
            "chain_code",
            "metric_code",
            "source_code",
            "obs_date",
            name="uq_observation_source_metric_day",
        ),
    )
    op.create_index(
        "ix_observations_chain_metric_date",
        "observations",
        ["chain_code", "metric_code", "obs_date"],
    )
    op.create_table(
        "series_coverage",
        sa.Column("chain_code", sa.String(16), nullable=False),
        sa.Column("metric_code", sa.String(64), nullable=False),
        sa.Column("source_code", sa.String(64), nullable=False),
        sa.Column("first_date", sa.Date(), nullable=True),
        sa.Column("last_date", sa.Date(), nullable=True),
        sa.Column("points", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("missing_days", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(300), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="never_run"),
        sa.ForeignKeyConstraint(["chain_code"], ["chains.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["metric_code"], ["metric_definitions.code"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_code"], ["data_sources.code"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("chain_code", "metric_code", "source_code"),
        sa.UniqueConstraint(
            "chain_code",
            "metric_code",
            "source_code",
            name="uq_series_coverage_triple",
        ),
    )
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rows_upserted", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_rejected", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(300), nullable=True),
        sa.CheckConstraint(
            "status IN ('running','ok','partial','error')",
            name="ck_ingestion_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_runs")
    op.drop_table("series_coverage")
    op.drop_index(
        "ix_observations_chain_metric_date",
        table_name="observations",
    )
    op.drop_table("observations")
    op.drop_table("metric_definitions")
    op.drop_table("data_sources")
    op.drop_table("chains")

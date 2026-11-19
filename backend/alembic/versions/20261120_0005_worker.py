"""Add worker run metadata and outcomes.

Revision ID: 20261120_0005
Revises: 20261119_0004
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261120_0005"
down_revision: str | None = "20261119_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingestion_runs", sa.Column("details", sa.Text(), nullable=True))
    op.drop_constraint(
        "ck_ingestion_runs_status",
        "ingestion_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ingestion_runs_status",
        "ingestion_runs",
        "status IN ('running','ok','partial','error','failed','rate_limited')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_runs_status",
        "ingestion_runs",
        type_="check",
    )
    op.execute(
        "UPDATE ingestion_runs SET status='error' "
        "WHERE status IN ('failed','rate_limited')"
    )
    op.create_check_constraint(
        "ck_ingestion_runs_status",
        "ingestion_runs",
        "status IN ('running','ok','partial','error')",
    )
    op.drop_column("ingestion_runs", "details")

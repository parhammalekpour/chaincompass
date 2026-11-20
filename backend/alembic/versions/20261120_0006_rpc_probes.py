"""Add sanitized RPC liveness probes.

Revision ID: 20261120_0006
Revises: 20261120_0005
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261120_0006"
down_revision: str | None = "20261120_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rpc_probes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chain_id", sa.String(length=16), nullable=False),
        sa.Column("provider_label", sa.String(length=64), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("block_height", sa.BigInteger(), nullable=True),
        sa.Column("block_age_seconds", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["chain_id"],
            ["chains.code"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE INDEX ix_rpc_probes_chain_provider_checked_desc "
        "ON rpc_probes (chain_id, provider_label, checked_at DESC)"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rpc_probes_chain_provider_checked_desc",
        table_name="rpc_probes",
    )
    op.drop_table("rpc_probes")

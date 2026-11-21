"""Add agent conversations, messages, and usage tables.

Revision ID: 20261121_0009
Revises: 20261120_0008
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261121_0009"
down_revision: str | None = "20261120_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chat_conversations_user_updated",
        "chat_conversations",
        ["user_id", "updated_at"],
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("grounding_status", sa.String(length=16), nullable=True),
        sa.Column("refusal", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'tool')", name="ck_chat_messages_role"
        ),
        sa.CheckConstraint(
            "grounding_status IS NULL OR grounding_status IN "
            "('ok', 'retried', 'failed', 'refused')",
            name="ck_chat_messages_grounding_status",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chat_messages_conversation_created",
        "chat_messages",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "llm_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["chat_conversations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_usage_user_created", "llm_usage", ["user_id", "created_at"])
    op.create_index("ix_llm_usage_conversation", "llm_usage", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_conversation", table_name="llm_usage")
    op.drop_index("ix_llm_usage_user_created", table_name="llm_usage")
    op.drop_table("llm_usage")
    op.drop_index("ix_chat_messages_conversation_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_conversations_user_updated", table_name="chat_conversations")
    op.drop_table("chat_conversations")

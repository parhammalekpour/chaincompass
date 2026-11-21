from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("ix_chat_conversations_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'tool')",
            name="ck_chat_messages_role",
        ),
        CheckConstraint(
            "grounding_status IS NULL OR grounding_status IN "
            "('ok', 'retried', 'failed', 'refused')",
            name="ck_chat_messages_grounding_status",
        ),
        Index("ix_chat_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[Literal["user", "assistant", "tool"]] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSONB, nullable=True
    )
    grounding_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    refusal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LLMUsage(Base):
    __tablename__ = "llm_usage"
    __table_args__ = (
        Index("ix_llm_usage_user_created", "user_id", "created_at"),
        Index("ix_llm_usage_conversation", "conversation_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("chat_conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

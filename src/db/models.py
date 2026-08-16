"""SQLAlchemy ORM 模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Integer, DateTime, Text, JSON, func, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


class AffectionModel(Base):
    """好感度表"""
    __tablename__ = "affection"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class EmotionModel(Base):
    """情绪状态表"""
    __tablename__ = "emotion"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    happy: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worried: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lonely: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sad: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    angry: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserProfileModel(Base):
    """用户画像表"""
    __tablename__ = "user_profile"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    facts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChatHistoryModel(Base):
    """对话历史表（含状态快照）"""
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # 'user' / 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotion: Mapped[str | None] = mapped_column(Text, nullable=True)
    affection_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    affection_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_chat_history_user_id_created_at", "user_id", "created_at"),
    )


class ConversationSummaryModel(Base):
    """对话摘要表"""
    __tablename__ = "conversation_summary"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # embedding 列通过 pgvector 扩展创建，使用 raw SQL 管理
    # SQL: ALTER TABLE conversation_summary ADD COLUMN embedding vector(512)
    start_round: Mapped[int] = mapped_column(Integer, nullable=False)
    end_round: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_conversation_summary_user_id_created_at", "user_id", "created_at"),
    )

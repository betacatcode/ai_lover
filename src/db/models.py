"""SQLAlchemy ORM 模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Integer, DateTime, func
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

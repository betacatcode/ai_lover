"""SQLAlchemy 异步会话管理"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base

# 异步引擎（全局单例）
_engine = None
_session_factory = None


def init_db(database_url: str) -> None:
    """
    初始化数据库引擎和会话工厂。

    Args:
        database_url: PostgreSQL 连接 URL，如 postgresql+asyncpg://user:pass@host:5432/dbname
    """
    global _engine, _session_factory

    # 将 postgresql:// 转换为 postgresql+asyncpg://
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    _engine = create_async_engine(database_url, echo=False, pool_size=5, max_overflow=10)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def close_db() -> None:
    """关闭数据库引擎"""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def create_tables() -> None:
    """创建所有表（首次启动时调用）"""
    if _engine is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话（依赖注入用）。

    用法：
        async with get_session() as session:
            session.add(obj)
            await session.commit()
    """
    if _session_factory is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    async with _session_factory() as session:
        yield session

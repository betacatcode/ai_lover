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
        # 启用 pgvector 扩展
        await conn.execute(__import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def create_vector_index(table_name: str, column_name: str = "embedding", dimension: int = 512) -> None:
    """
    为表的向量列创建 ivfflat 索引。

    Args:
        table_name: 表名
        column_name: 向量列名
        dimension: 向量维度
    """
    if _engine is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")

    # 检查列是否存在且类型正确（pgvector）
    from sqlalchemy import text
    async with _engine.begin() as conn:
        # 添加向量列（如果不存在）
        try:
            await conn.execute(text(
                f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} vector({dimension})"
            ))
        except Exception:
            pass  # 列已存在或类型已正确

        # 创建 ivfflat 索引
        index_name = f"idx_{table_name}_{column_name}"
        await conn.execute(text(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} "
            f"USING ivfflat ({column_name} vector_cosine_ops) WITH (lists = 100)"
        ))


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

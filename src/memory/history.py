"""对话历史存储 — PostgreSQL 持久化"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class HistoryRepository:
    """
    对话历史存储。

    支持内存和 PostgreSQL 两种后端。
    """

    def __init__(self, database_url: str | None = None, window_size: int = 10) -> None:
        self._db_url = database_url
        self._window_size = window_size
        self._memory_store: dict[int, list[dict]] = {}

    async def save_round(
        self,
        user_id: int,
        user_message: str,
        ai_reply: str,
        raw_reply: str,
        emotion: str = "",
        affection_level: int = 0,
        affection_points: int = 0,
    ) -> None:
        """
        保存一轮对话。

        同时写入 user 和 assistant 两条记录。
        """
        if self._db_url:
            await self._save_to_db(
                user_id, user_message, ai_reply, raw_reply,
                emotion, affection_level, affection_points,
            )
        else:
            await self._save_to_memory(
                user_id, user_message, ai_reply, raw_reply,
                emotion, affection_level, affection_points,
            )

    async def get_recent(self, user_id: int, rounds: int | None = None) -> list[dict]:
        """
        获取最近 N 轮对话。

        Returns:
            消息列表 [{"role": "user"|"assistant", "content": "..."}, ...]
        """
        if self._db_url:
            return await self._get_recent_from_db(user_id, rounds or self._window_size)
        messages = self._memory_store.get(user_id, [])
        # 返回最近 N 轮（2N 条消息）
        return messages[-(rounds or self._window_size) * 2:]

    async def get_recent_text(self, user_id: int, rounds: int = 10) -> str:
        """
        获取最近 N 轮对话的纯文本格式（用于 LLM 处理）。

        Returns:
            格式化的对话文本
        """
        messages = await self.get_recent(user_id, rounds)
        lines = []
        for msg in messages:
            role = "用户" if msg.get("role") == "user" else "诺艾尔"
            content = msg.get("content", "")
            lines.append(f"{role}：{content}")
        return "\n".join(lines)

    async def load_to_memory(self, user_id: int) -> list[dict]:
        """
        从 DB 加载最近 N 轮到内存（服务启动时调用）。

        Returns:
            消息列表
        """
        messages = await self.get_recent(user_id, self._window_size)
        self._memory_store[user_id] = messages
        return messages

    # ── 内存存储 ──

    async def _save_to_memory(
        self,
        user_id: int,
        user_message: str,
        ai_reply: str,
        raw_reply: str,
        emotion: str,
        affection_level: int,
        affection_points: int,
    ) -> None:
        """内存模式：保存"""
        if user_id not in self._memory_store:
            self._memory_store[user_id] = []

        history = self._memory_store[user_id]
        history.append({"role": "user", "content": user_message})
        history.append({
            "role": "assistant",
            "content": ai_reply,
            "raw_content": raw_reply,
            "emotion": emotion,
            "affection_level": affection_level,
            "affection_points": affection_points,
        })

        # 裁剪
        max_len = self._window_size * 2
        if len(history) > max_len:
            self._memory_store[user_id] = history[-max_len:]

    # ── PostgreSQL 存储 ──

    async def _save_to_db(
        self,
        user_id: int,
        user_message: str,
        ai_reply: str,
        raw_reply: str,
        emotion: str,
        affection_level: int,
        affection_points: int,
    ) -> None:
        """PostgreSQL 模式：保存"""
        from ..db.models import ChatHistoryModel
        from ..db.session import get_session

        async for session in get_session():
            # 用户消息
            user_record = ChatHistoryModel(
                user_id=user_id,
                role="user",
                content=user_message,
            )
            session.add(user_record)

            # AI 回复
            assistant_record = ChatHistoryModel(
                user_id=user_id,
                role="assistant",
                content=ai_reply,
                raw_content=raw_reply if raw_reply != ai_reply else None,
                emotion=emotion,
                affection_level=affection_level,
                affection_points=affection_points,
            )
            session.add(assistant_record)

            await session.commit()

    async def _get_recent_from_db(self, user_id: int, rounds: int) -> list[dict]:
        """PostgreSQL 模式：读取"""
        from ..db.models import ChatHistoryModel
        from ..db.session import get_session
        from sqlalchemy import select, desc

        async for session in get_session():
            result = await session.execute(
                select(ChatHistoryModel)
                .where(ChatHistoryModel.user_id == user_id)
                .order_by(desc(ChatHistoryModel.created_at))
                .limit(rounds * 2)
            )
            records = result.scalars().all()
            # 反转顺序（从旧到新）
            records = list(reversed(records))
            return [
                {
                    "role": r.role,
                    "content": r.content,
                    "raw_content": r.raw_content,
                    "emotion": r.emotion,
                    "affection_level": r.affection_level,
                    "affection_points": r.affection_points,
                }
                for r in records
            ]
        return []

"""对话历史管理 — 滑动窗口，按 user_id 隔离（MVP 内存存储）"""

from __future__ import annotations

import logging
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)


class ChatHistoryManager:
    """
    内存对话历史管理器。

    按 user_id 隔离，每个用户保留最近 N 轮对话。
    MVP 阶段存内存，后续可替换为 PostgreSQL 持久化。
    """

    def __init__(self, window_size: int = 15):
        self._window_size = window_size
        # {user_id: [{"role": "user"|"assistant", "content": "..."}, ...]}
        self._histories: dict[int, list[dict]] = defaultdict(list)
        self._lock = Lock()
        logger.info("ChatHistoryManager 初始化: window_size=%d", window_size)

    def add_message(self, user_id: int, role: str, content: str) -> None:
        """添加一条消息到用户的历史"""
        with self._lock:
            history = self._histories[user_id]
            history.append({"role": role, "content": content})
            # 超出窗口时裁剪早期消息
            if len(history) > self._window_size * 2:  # *2 因为每轮有 user + assistant
                excess = len(history) - self._window_size * 2
                self._histories[user_id] = history[excess:]
                logger.debug("用户 %d 历史裁剪: 移除 %d 条", user_id, excess)

    def get_history(self, user_id: int) -> list[dict]:
        """获取用户的对话历史（返回副本）"""
        with self._lock:
            return list(self._histories.get(user_id, []))

    def reset_history(self, user_id: int) -> None:
        """重置用户对话历史"""
        with self._lock:
            if user_id in self._histories:
                del self._histories[user_id]
                logger.info("用户 %d 对话历史已重置", user_id)

    @property
    def window_size(self) -> int:
        return self._window_size

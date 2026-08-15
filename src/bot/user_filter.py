"""用户过滤中间件 — 仅允许配置的用户与 Bot 交互"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)


class UserFilterMiddleware(BaseMiddleware):
    """只响应 allowed_user_id 的消息，其他用户发来的消息静默忽略"""

    def __init__(self, allowed_user_id: int):
        self.allowed_user_id = allowed_user_id

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        user = event.from_user
        if user is None:
            return  # 匿名消息忽略

        if user.id != self.allowed_user_id:
            logger.warning(
                "未授权用户尝试交互: user_id=%d, username=%s",
                user.id,
                user.username,
            )
            # 静默忽略，不回复任何内容
            return

        return await handler(event, data)

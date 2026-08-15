"""聊天服务 — 统一入口，编排历史/Prompt/LLM"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import AppConfig
from ..llm.client import LLMClient
from ..llm.exceptions import LLMError, LLMTimeoutError
from ..systems.affection import AffectionSystem, InMemoryAffectionRepository
from .filter import filter_reply
from .history import ChatHistoryManager
from .prompt import build_system_prompt

logger = logging.getLogger(__name__)

# LLM 失败时的降级回复
FALLBACK_REPLIES = [
    "抱歉，诺艾尔现在有点走神了……能再说一遍吗？",
    "啊，不好意思！刚刚没听清，可以再说一次吗？",
    "嗯？抱歉抱歉，诺艾尔没反应过来，请再说一遍～",
]


@dataclass
class ChatResult:
    """聊天结果（含 debug 信息）"""
    reply: str
    affection_level: str
    affection_points: int
    affection_delta: int
    emotion: str = "平静"


class ChatService:
    """
    聊天业务层统一入口。

    被 Telegram Bot 和 FastAPI 共同调用，管理对话历史、组装 Prompt、调用 LLM。

    用法：
        service = ChatService(llm_client, config)
        reply = await service.chat(user_id=123, message="你好")
    """

    def __init__(self, llm_client: LLMClient, config: AppConfig):
        self._llm = llm_client
        self._config = config
        self._history = ChatHistoryManager(window_size=config.chat.history_window)

        # 好感度系统（MVP 使用内存存储，后续可替换为 PostgreSQL）
        # 传入 llm_client 用于 LLM 评估好感度变化
        affection_repo = InMemoryAffectionRepository()
        self._affection = AffectionSystem(
            repository=affection_repo,
            llm_client=llm_client,
            initial_level=config.affection.initial_level,
            initial_points=config.affection.initial_points,
        )
        logger.info("ChatService 初始化完成（好感度系统已启用，LLM 评估模式）")

    async def chat(self, user_id: int, message: str) -> ChatResult:
        """
        处理用户消息并返回诺艾尔的回复。

        Args:
            user_id: 用户 ID
            message: 用户消息文本

        Returns:
            ChatResult 含回复文本和 debug 信息
        """
        logger.info("聊天请求: user_id=%d, message=%r", user_id, message[:50])

        # 1. 获取当前好感度状态（用于 Prompt 组装）
        affection_state = await self._affection.get_state(user_id)

        # 2. 组装 system prompt（含好感度层）
        system_prompt = build_system_prompt(affection_state=affection_state)

        # 3. 获取历史 + 当前消息
        history = self._history.get_history(user_id)
        messages = history + [{"role": "user", "content": message}]

        # 4. 调用 LLM 生成回复（带降级处理）
        try:
            reply = await self._llm.complete(messages, system_prompt=system_prompt)
        except LLMTimeoutError:
            logger.warning("LLM 超时，使用降级回复: user_id=%d", user_id)
            reply = FALLBACK_REPLIES[0]
        except LLMError as e:
            logger.error("LLM 错误，使用降级回复: %s", e)
            reply = FALLBACK_REPLIES[hash(user_id) % len(FALLBACK_REPLIES)]

        # 5. 后处理过滤（根据好感度/情绪调整长度、去除格式符号）
        reply = filter_reply(reply, affection_state.level.value)

        # 6. LLM 评估好感度变化（传入用户消息 + 诺艾尔回复作为上下文）
        affection_result = await self._affection.process_message(user_id, message, reply)

        # 7. 保存到历史
        self._history.add_message(user_id, "user", message)
        self._history.add_message(user_id, "assistant", reply)

        logger.info("聊天回复: user_id=%d, reply=%d chars, affection=%s(%d, delta=%d)",
                    user_id, len(reply),
                    affection_result.new_state.level.title,
                    affection_result.new_state.points,
                    affection_result.points_delta)

        return ChatResult(
            reply=reply,
            affection_level=affection_result.new_state.level.title,
            affection_points=affection_result.new_state.points,
            affection_delta=affection_result.points_delta,
            emotion=self._config.emotion.default,
        )

    def get_history(self, user_id: int) -> list[dict]:
        """获取用户对话历史"""
        return self._history.get_history(user_id)

    def reset_history(self, user_id: int) -> None:
        """重置用户对话历史"""
        self._history.reset_history(user_id)

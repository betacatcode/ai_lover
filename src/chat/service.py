"""聊天服务 — 统一入口，编排历史/Prompt/LLM/情绪/记忆"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import AppConfig
from ..llm.client import LLMClient
from ..llm.exceptions import LLMError, LLMTimeoutError
from ..systems.affection import AffectionSystem, InMemoryAffectionRepository, PostgresAffectionRepository
from ..systems.emotion import EmotionSystem, InMemoryEmotionRepository, PostgresEmotionRepository
from ..memory.memory_system import MemorySystem
from ..memory.history import HistoryRepository
from ..memory.profile import ProfileRepository
from ..memory.summary import SummaryRepository
from ..memory.embedding import get_embedding_service
from ..memory.retriever import MemoryRetriever
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

    被 Telegram Bot 和 FastAPI 共同调用，管理对话历史、组装 Prompt、调用 LLM、更新情绪。

    用法：
        service = ChatService(llm_client, config)
        result = await service.chat(user_id=123, message="你好")
    """

    def __init__(self, llm_client: LLMClient, config: AppConfig):
        self._llm = llm_client
        self._config = config
        self._history = ChatHistoryManager(window_size=config.chat.history_window)

        db_url = config.memory.db.url

        # 好感度系统（DB 持久化）
        affection_repo = PostgresAffectionRepository(db_url)
        self._affection = AffectionSystem(
            repository=affection_repo,
            llm_client=llm_client,
            initial_level=config.affection.initial_level,
            initial_points=config.affection.initial_points,
        )

        # 情绪系统（DB 持久化）
        emotion_repo = PostgresEmotionRepository(db_url)
        self._emotion = EmotionSystem(
            repository=emotion_repo,
            llm_client=llm_client,
            decay_interval_minutes=config.emotion.decay_interval_minutes,
            decay_amount=config.emotion.decay_amount,
        )

        # 记忆系统
        self._embedding = get_embedding_service(
            model_name=config.memory.embedding.model,
            dimension=config.memory.embedding.dimension,
        )
        self._history_repo = HistoryRepository(database_url=db_url, window_size=config.chat.history_window)
        self._profile_repo = ProfileRepository(database_url=db_url)
        self._summary_repo = SummaryRepository(database_url=db_url, embedding_service=self._embedding)
        self._retriever = MemoryRetriever(
            embedding_service=self._embedding,
            summary_repo=self._summary_repo,
            profile_repo=self._profile_repo,
        )
        self._memory = MemorySystem(
            llm_client=llm_client,
            embedding_service=self._embedding,
            profile_repo=self._profile_repo,
            summary_repo=self._summary_repo,
            retriever=self._retriever,
            history_repo=self._history_repo,
            trigger_rounds=config.chat.history_window,  # 与滑动窗口一致
        )

        logger.info("ChatService 初始化完成（好感度+情绪+记忆系统已启用，LLM 评估模式）")

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

        # 1. 获取当前好感度、情绪、记忆状态（用于 Prompt 组装）
        affection_state = await self._affection.get_state(user_id)
        emotion_state = await self._emotion.get_state(user_id)
        memory_state = await self._memory.get_state(user_id, current_message=message)

        # 2. 组装 system prompt（含好感度层 + 情绪层 + 记忆层）
        system_prompt = build_system_prompt(
            affection_state=affection_state,
            emotion_state=emotion_state,
            memory_state=memory_state,
        )

        # 3. 获取历史 + 当前消息
        history = self._history.get_history(user_id)
        messages = history + [{"role": "user", "content": message}]

        # 4. 调用 LLM 生成回复（带降级处理）
        try:
            raw_reply = await self._llm.complete(messages, system_prompt=system_prompt)
        except LLMTimeoutError:
            logger.warning("LLM 超时，使用降级回复: user_id=%d", user_id)
            raw_reply = FALLBACK_REPLIES[0]
        except LLMError as e:
            logger.error("LLM 错误，使用降级回复: %s", e)
            raw_reply = FALLBACK_REPLIES[hash(user_id) % len(FALLBACK_REPLIES)]

        # 5. 后处理过滤（根据好感度/情绪调整长度、去除格式符号）
        filtered_reply = filter_reply(raw_reply, affection_state.level.value, emotion_state.current_emotion.value)

        # 6. LLM 评估好感度变化
        affection_result = await self._affection.process_message(user_id, message, filtered_reply)

        # 7. LLM 评估情绪变化
        emotion_result = await self._emotion.process_message(user_id, message, filtered_reply)

        # 8. 情绪冷却递减（每轮对话后 -1）
        emotion_result.state.tick_cooldown()
        await self._emotion._repo.save(emotion_result.state)

        # 9. 保存到历史（内存 + DB）
        self._history.add_message(user_id, "user", message)
        self._history.add_message(user_id, "assistant", filtered_reply)

        # 10. 记忆系统：写入历史 + 检查触发
        await self._memory.after_round(
            user_id=user_id,
            user_message=message,
            ai_reply=filtered_reply,
            raw_reply=raw_reply,
            emotion=emotion_result.state.current_emotion.value,
            affection_level=affection_result.new_state.level.value,
            affection_points=affection_result.new_state.points,
        )

        logger.info(
            "聊天回复: user_id=%d, reply=%d chars, affection=%s(%d, delta=%d), emotion=%s, memory=%s",
            user_id, len(filtered_reply),
            affection_result.new_state.level.title,
            affection_result.new_state.points,
            affection_result.points_delta,
            emotion_result.state.current_emotion.value,
            "有" if memory_state.has_memory else "无",
        )

        return ChatResult(
            reply=filtered_reply,
            affection_level=affection_result.new_state.level.title,
            affection_points=affection_result.new_state.points,
            affection_delta=affection_result.points_delta,
            emotion=emotion_result.state.current_emotion.value,
        )

    def get_history(self, user_id: int) -> list[dict]:
        """获取用户对话历史"""
        return self._history.get_history(user_id)

    def reset_history(self, user_id: int) -> None:
        """重置用户对话历史"""
        self._history.reset_history(user_id)

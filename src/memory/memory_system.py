"""记忆系统主类 — 统一入口，编排画像/摘要/检索"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MemoryState:
    """记忆状态（用于 Prompt 注入）"""
    profile_text: str = ""       # Layer 4: 用户画像文本
    recent_summaries: list[str] = field(default_factory=list)  # 最近摘要
    retrieved_memories: list[str] = field(default_factory=list)  # 语义检索结果

    @property
    def has_memory(self) -> bool:
        """是否有任何记忆"""
        return bool(self.profile_text or self.recent_summaries or self.retrieved_memories)

    def get_profile_layer(self) -> str:
        """获取 Layer 4 文本"""
        if not self.profile_text:
            return ""
        return f"## 你了解到的关于用户的信息\n{self.profile_text}"

    def get_memory_layer(self) -> str:
        """获取 Layer 5 文本"""
        parts = []

        if self.recent_summaries:
            parts.append("【最近摘要】")
            parts.extend(self.recent_summaries)

        if self.retrieved_memories:
            parts.append("\n【相关记忆】")
            parts.extend(self.retrieved_memories)

        return "\n".join(parts) if parts else ""


class MemorySystem:
    """
    记忆系统统一入口。

    用法:
        memory = MemorySystem(
            llm_client=llm,
            embedding_service=embedding,
            profile_repo=profile_repo,
            summary_repo=summary_repo,
            retriever=retriever,
            history_repo=history_repo,
            trigger_rounds=10,
        )
        # 获取记忆状态（用于 Prompt）
        state = await memory.get_state(user_id, current_message)
        # 对话结束后处理
        await memory.after_round(user_id, user_msg, ai_reply, raw_reply)
    """

    def __init__(
        self,
        llm_client=None,
        embedding_service=None,
        profile_repo=None,
        summary_repo=None,
        retriever=None,
        history_repo=None,
        trigger_rounds: int = 10,
    ) -> None:
        self._llm = llm_client
        self._embedding = embedding_service
        self._profile_repo = profile_repo
        self._summary_repo = summary_repo
        self._retriever = retriever
        self._history_repo = history_repo
        self._trigger_rounds = trigger_rounds
        # 对话轮次计数器（内存，重启后从 DB 恢复）
        self._round_counters: dict[int, int] = {}

    async def get_state(self, user_id: int, current_message: str = "") -> MemoryState:
        """
        获取记忆状态（用于 Prompt 注入）。

        Args:
            user_id: 用户 ID
            current_message: 当前用户消息（用于语义检索）

        Returns:
            MemoryState 包含画像、摘要、检索结果
        """
        state = MemoryState()

        # Layer 4: 用户画像
        if self._profile_repo:
            state.profile_text = await self._profile_repo.get_formatted(user_id)

        # Layer 5: 最近摘要
        if self._retriever:
            state.recent_summaries = await self._retriever.get_recent_summaries(user_id, limit=2)

            # Layer 5: 语义检索（如果有当前消息）
            if current_message:
                state.retrieved_memories = await self._retriever.search(user_id, current_message, top_k=3)

        return state

    async def after_round(
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
        对话结束后处理。

        1. 写入 chat_history
        2. 检查是否触发画像提取 + 摘要生成

        Args:
            user_id: 用户 ID
            user_message: 用户消息
            ai_reply: AI 回复（过滤后）
            raw_reply: AI 原始回复
            emotion: 当前情绪
            affection_level: 当前好感度等级
            affection_points: 当前好感度分数
        """
        # 写入历史
        if self._history_repo:
            await self._history_repo.save_round(
                user_id=user_id,
                user_message=user_message,
                ai_reply=ai_reply,
                raw_reply=raw_reply,
                emotion=emotion,
                affection_level=affection_level,
                affection_points=affection_points,
            )

        # 更新轮次计数
        current_round = self._round_counters.get(user_id, 0) + 1
        self._round_counters[user_id] = current_round

        # 检查触发条件
        if current_round % self._trigger_rounds == 0:
            logger.info("触发记忆处理: user_id=%d, 轮次=%d", user_id, current_round)
            await self._trigger_memory_processing(user_id, current_round)

    async def _trigger_memory_processing(self, user_id: int, end_round: int) -> None:
        """触发画像提取和摘要生成"""
        start_round = end_round - self._trigger_rounds + 1

        # 读取最近 N 轮对话
        if not self._history_repo:
            return

        conversation = await self._history_repo.get_recent_text(user_id, rounds=self._trigger_rounds)
        if not conversation:
            return

        # 画像提取
        if self._profile_repo and self._llm:
            from .profile import ProfileExtractor
            extractor = ProfileExtractor(self._llm)
            facts = await extractor.extract(conversation)
            if facts:
                await self._profile_repo.upsert(user_id, facts)

        # 摘要生成
        if self._summary_repo and self._llm:
            from .summary import SummaryGenerator
            generator = SummaryGenerator(self._llm)
            summary = await generator.generate(conversation, start_round, end_round)
            if summary:
                await self._summary_repo.save(user_id, summary)

    def reset_counter(self, user_id: int) -> None:
        """重置轮次计数器（/reset 命令时调用）"""
        if user_id in self._round_counters:
            del self._round_counters[user_id]

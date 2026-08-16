"""记忆检索器 — 向量语义检索"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class MemoryRetriever:
    """
    记忆检索器。

    结合摘要和画像进行语义检索。
    """

    def __init__(self, embedding_service, summary_repo, profile_repo) -> None:
        self._embedding = embedding_service
        self._summary_repo = summary_repo
        self._profile_repo = profile_repo

    async def search(self, user_id: int, query: str, top_k: int = 3) -> list[str]:
        """
        检索与查询相关的记忆片段。

        Args:
            user_id: 用户 ID
            query: 查询文本（当前用户消息）
            top_k: 返回数量

        Returns:
            相关记忆片段文本列表
        """
        if not self._embedding or not self._embedding.is_loaded:
            logger.debug("Embedding 不可用，跳过记忆检索")
            return []

        # 生成查询向量
        query_embedding = self._embedding.encode(query)

        # 检索摘要
        summaries = await self._summary_repo.search(user_id, query_embedding, top_k)

        # 格式化结果
        results = []
        for s in summaries:
            content = s.get("content", "")
            if content:
                results.append(content)

        logger.debug("记忆检索完成: %d 条结果", len(results))
        return results

    async def get_recent_summaries(self, user_id: int, limit: int = 2) -> list[str]:
        """
        获取最近 N 段摘要（固定注入）。

        Args:
            user_id: 用户 ID
            limit: 数量

        Returns:
            摘要文本列表
        """
        summaries = await self._summary_repo.get_recent(user_id, limit)
        return [s.get("content", "") for s in summaries if s.get("content")]

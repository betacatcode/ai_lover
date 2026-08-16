"""对话摘要系统 — 压缩对话历史为摘要"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# ── LLM 摘要 Prompt ──

_SUMMARY_PROMPT = """你是诺艾尔（Noelle），西风骑士团的女仆。现在需要你对最近的对话生成一段摘要。

## 对话内容
{conversation}

## 摘要要求
请生成一段简洁的中文摘要（100-200字），包含：
1. 讨论的主要话题
2. 用户表达的重要信息（偏好、近况、情绪等）
3. 诺艾尔做出的承诺或约定
4. 用户情绪变化（如果有）

## 输出格式
返回 JSON 对象：
{{"content": "摘要文本"}}

只返回 JSON，不要其他内容。"""


@dataclass
class Summary:
    """对话摘要"""
    content: str
    start_round: int
    end_round: int
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class SummaryGenerator:
    """
    对话摘要生成器。

    调用 LLM 将多轮对话压缩为摘要。
    """

    def __init__(self, llm_client=None) -> None:
        self._llm = llm_client

    async def generate(self, conversation: str, start_round: int, end_round: int) -> Summary | None:
        """
        生成对话摘要。

        Args:
            conversation: 对话文本
            start_round: 起始轮次
            end_round: 结束轮次

        Returns:
            生成的摘要，失败返回 None
        """
        if self._llm is None:
            return None

        prompt = _SUMMARY_PROMPT.format(conversation=conversation)

        try:
            result = await self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=None,
            )
            content = self._parse_response(result)
            if content:
                summary = Summary(
                    content=content,
                    start_round=start_round,
                    end_round=end_round,
                )
                logger.debug("摘要生成完成: %d-%d 轮, %d 字", start_round, end_round, len(content))
                return summary
            return None
        except Exception as e:
            logger.warning("摘要生成失败: %s", e)
            return None

    def _parse_response(self, response: str) -> str | None:
        """解析 LLM 返回的 JSON"""
        json_match = re.search(r"\{[\s\S]*\}", response.strip())
        if not json_match:
            return None

        try:
            data = json.loads(json_match.group())
            content = data.get("content", "")
            return content if content else None
        except json.JSONDecodeError:
            logger.warning("摘要 JSON 解析失败: %s", response[:100])
            return None


class SummaryRepository:
    """
    对话摘要存储。

    支持内存和 PostgreSQL + pgvector 两种后端。
    """

    def __init__(self, database_url: str | None = None, embedding_service=None) -> None:
        self._db_url = database_url
        self._embedding = embedding_service
        self._memory_store: dict[int, list[dict]] = {}

    async def save(self, user_id: int, summary: Summary) -> None:
        """保存摘要"""
        if self._db_url:
            await self._save_to_db(user_id, summary)
        else:
            await self._save_to_memory(user_id, summary)

    async def get_recent(self, user_id: int, limit: int = 2) -> list[dict]:
        """获取最近 N 段摘要"""
        if self._db_url:
            return await self._get_recent_from_db(user_id, limit)
        summaries = self._memory_store.get(user_id, [])
        return summaries[-limit:]

    async def search(self, user_id: int, query_embedding: list[float], top_k: int = 3) -> list[dict]:
        """
        语义检索最相关的摘要。

        Args:
            user_id: 用户 ID
            query_embedding: 查询向量
            top_k: 返回数量

        Returns:
            最相关的摘要列表，按相似度排序
        """
        if self._db_url and self._embedding:
            return await self._search_in_db(user_id, query_embedding, top_k)
        # 内存模式：返回最近 N 条
        return await self.get_recent(user_id, top_k)

    async def get_formatted(self, user_id: int, limit: int = 2) -> str:
        """
        获取格式化的摘要文本（用于 Prompt 注入）。

        Returns:
            格式化的文本，无摘要时返回空字符串
        """
        summaries = await self.get_recent(user_id, limit)
        if not summaries:
            return ""

        lines = []
        for s in summaries:
            content = s.get("content", "")
            if content:
                lines.append(content)

        return "\n\n".join(lines)

    # ── 内存存储 ──

    async def _save_to_memory(self, user_id: int, summary: Summary) -> None:
        if user_id not in self._memory_store:
            self._memory_store[user_id] = []
        self._memory_store[user_id].append({
            "content": summary.content,
            "start_round": summary.start_round,
            "end_round": summary.end_round,
            "created_at": summary.created_at,
        })

    async def _get_recent_from_db(self, user_id: int, limit: int) -> list[dict]:
        from ..db.models import ConversationSummaryModel
        from ..db.session import get_session
        from sqlalchemy import select, desc

        async for session in get_session():
            result = await session.execute(
                select(ConversationSummaryModel)
                .where(ConversationSummaryModel.user_id == user_id)
                .order_by(desc(ConversationSummaryModel.created_at))
                .limit(limit)
            )
            summaries = result.scalars().all()
            return [
                {
                    "content": s.content,
                    "start_round": s.start_round,
                    "end_round": s.end_round,
                    "created_at": s.created_at.isoformat() if s.created_at else "",
                }
                for s in summaries
            ]
        return []

    async def _save_to_db(self, user_id: int, summary: Summary) -> None:
        from ..db.models import ConversationSummaryModel
        from ..db.session import get_session
        from sqlalchemy import text

        # 生成 embedding
        embedding = None
        if self._embedding and self._embedding.is_loaded:
            embedding = self._embedding.encode(summary.content)

        async for session in get_session():
            model = ConversationSummaryModel(
                user_id=user_id,
                content=summary.content,
                start_round=summary.start_round,
                end_round=summary.end_round,
            )
            session.add(model)
            await session.flush()  # 获取 ID

            # 更新 embedding（raw SQL，因为 SQLAlchemy 不支持 vector 类型）
            if embedding:
                await session.execute(
                    text("UPDATE conversation_summary SET embedding = :emb WHERE id = :id"),
                    {"emb": str(embedding).replace("[", "[").replace("]", "]"), "id": model.id},
                )

            await session.commit()

    async def _search_in_db(self, user_id: int, query_embedding: list[float], top_k: int) -> list[dict]:
        """pgvector 余弦相似度检索"""
        from ..db.session import get_session
        from sqlalchemy import text

        # 检查 embedding 列是否存在
        async for session in get_session():
            try:
                result = await session.execute(
                    text(
                        "SELECT id, content, start_round, end_round, "
                        "embedding <=> :query AS distance "
                        "FROM conversation_summary "
                        "WHERE user_id = :uid AND embedding IS NOT NULL "
                        "ORDER BY distance LIMIT :limit"
                    ),
                    {
                        "query": str(query_embedding),
                        "uid": user_id,
                        "limit": top_k,
                    },
                )
                rows = result.fetchall()
                return [
                    {
                        "id": row[0],
                        "content": row[1],
                        "start_round": row[2],
                        "end_round": row[3],
                        "distance": row[4],
                    }
                    for row in rows
                ]
            except Exception as e:
                logger.warning("向量检索失败: %s", e)
                return []
        return []


def build_memory_prompt_layer(user_id: int, summary_repo: SummaryRepository) -> str:
    """
    构建 Layer 5 对话记忆 Prompt。

    这是占位符，实际注入在 MemorySystem 中异步完成。
    """
    return ""

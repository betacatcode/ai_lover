"""用户画像系统 — 从对话中提取结构化事实"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# ── LLM 提取 Prompt ──

_PROFILE_EXTRACTION_PROMPT = """你是诺艾尔（Noelle），西风骑士团的女仆。现在需要你从最近的对话中提取关于用户的结构化信息。

## 最近对话
{conversation}

## 提取任务
请从对话中提取用户的基本信息，包括：
- 姓名/称呼
- 职业/工作
- 兴趣爱好（喜欢什么、讨厌什么）
- 宠物/家人
- 近期重要事件
- 个性特征

## 规则
1. 只提取用户明确说过的事实，不要推测
2. 如果对话中没有新信息，返回空列表
3. 如果用户修正了之前的信息（如"其实我不喜欢猫了"），记录新的信息

## 输出格式
返回 JSON 数组，每个元素格式：
[{{"key": "类别", "value": "具体信息"}}]

例如：
[{{"key": "name", "value": "小明"}}, {{"key": "pet", "value": "养了一只猫"}}]]

只返回 JSON，不要其他内容。"""


@dataclass
class ProfileFact:
    """单条用户画像事实"""
    key: str
    value: str
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ProfileExtractor:
    """
    用户画像提取器。

    调用 LLM 从对话中提取结构化事实。
    """

    def __init__(self, llm_client=None) -> None:
        self._llm = llm_client

    async def extract(self, conversation: str) -> list[ProfileFact]:
        """
        从对话中提取用户画像事实。

        Args:
            conversation: 对话文本（多轮）

        Returns:
            提取到的事实列表，无新信息或 LLM 不可用时返回空列表
        """
        if self._llm is None:
            return []

        prompt = _PROFILE_EXTRACTION_PROMPT.format(conversation=conversation)

        try:
            result = await self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=None,
            )
            facts = self._parse_response(result)
            logger.debug("画像提取完成: %d 条事实", len(facts))
            return facts
        except Exception as e:
            logger.warning("画像提取失败: %s", e)
            return []

    def _parse_response(self, response: str) -> list[ProfileFact]:
        """解析 LLM 返回的 JSON"""
        # 提取 JSON 数组
        json_match = re.search(r"\[[\s\S]*\]", response.strip())
        if not json_match:
            return []

        try:
            data = json.loads(json_match.group())
            if not isinstance(data, list):
                return []

            facts = []
            for item in data:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    facts.append(ProfileFact(
                        key=str(item["key"]),
                        value=str(item["value"]),
                    ))
            return facts
        except json.JSONDecodeError:
            logger.warning("画像提取 JSON 解析失败: %s", response[:100])
            return []


class ProfileRepository:
    """
    用户画像存储。

    支持内存和 PostgreSQL 两种后端。
    """

    def __init__(self, database_url: str | None = None) -> None:
        self._db_url = database_url
        self._memory_store: dict[int, list[dict]] = {}  # 内存回退

    async def get(self, user_id: int) -> list[dict]:
        """获取用户画像事实列表"""
        if self._db_url:
            return await self._get_from_db(user_id)
        return self._memory_store.get(user_id, [])

    async def upsert(self, user_id: int, new_facts: list[ProfileFact], max_facts: int = 10) -> None:
        """
        合并插入画像事实。

        已存在的 key 更新 value，新 key 插入。
        超过 max_facts 时按 updated_at 淘汰最旧的。
        """
        if self._db_url:
            await self._upsert_to_db(user_id, new_facts, max_facts)
        else:
            await self._upsert_to_memory(user_id, new_facts, max_facts)

    async def get_formatted(self, user_id: int, max_facts: int = 10) -> str:
        """
        获取格式化的画像文本（用于 Prompt 注入）。

        Returns:
            格式化的文本，无画像时返回空字符串
        """
        facts = await self.get(user_id)
        if not facts:
            return ""

        # 按 updated_at 排序，取最新
        sorted_facts = sorted(facts, key=lambda f: f.get("updated_at", ""), reverse=True)[:max_facts]

        lines = []
        for fact in sorted_facts:
            key = fact.get("key", "")
            value = fact.get("value", "")
            if key and value:
                lines.append(f"- {key}：{value}")

        return "\n".join(lines)

    # ── 内存存储 ──

    async def _upsert_to_memory(self, user_id: int, new_facts: list[ProfileFact], max_facts: int) -> None:
        """内存模式：合并插入"""
        existing = self._memory_store.get(user_id, [])
        fact_map = {f["key"]: f for f in existing}

        for fact in new_facts:
            fact_map[fact.key] = {
                "key": fact.key,
                "value": fact.value,
                "updated_at": fact.updated_at,
            }

        # 淘汰旧事实
        merged = sorted(fact_map.values(), key=lambda f: f.get("updated_at", ""), reverse=True)
        self._memory_store[user_id] = merged[:max_facts]

    async def _get_from_db(self, user_id: int) -> list[dict]:
        """PostgreSQL 模式：读取"""
        from ..db.models import UserProfileModel
        from ..db.session import get_session
        from sqlalchemy import select

        async for session in get_session():
            result = await session.execute(
                select(UserProfileModel).where(UserProfileModel.user_id == user_id)
            )
            model = result.scalar_one_or_none()
            if model is None:
                return []
            return model.facts or []
        return []

    async def _upsert_to_db(self, user_id: int, new_facts: list[ProfileFact], max_facts: int) -> None:
        """PostgreSQL 模式：合并插入"""
        from ..db.models import UserProfileModel
        from ..db.session import get_session
        from sqlalchemy import select

        async for session in get_session():
            result = await session.execute(
                select(UserProfileModel).where(UserProfileModel.user_id == user_id)
            )
            model = result.scalar_one_or_none()

            if model is None:
                model = UserProfileModel(user_id=user_id, facts=[])
                session.add(model)

            # 合并
            fact_map = {f["key"]: f for f in (model.facts or [])}
            for fact in new_facts:
                fact_map[fact.key] = {
                    "key": fact.key,
                    "value": fact.value,
                    "updated_at": fact.updated_at,
                }

            # 淘汰旧事实
            merged = sorted(fact_map.values(), key=lambda f: f.get("updated_at", ""), reverse=True)
            model.facts = merged[:max_facts]

            await session.commit()


def build_profile_prompt_layer(user_id: int, profile_repo: ProfileRepository) -> str:
    """
    构建 Layer 4 用户画像 Prompt。

    这是异步函数的同步包装，实际使用时应先调用 repo.get_formatted()。

    Args:
        user_id: 用户 ID
        profile_repo: 画像存储实例

    Returns:
        Layer 4 文本，无画像时返回空字符串
    """
    # 注意：这是占位符，实际注入在 MemorySystem 中异步完成
    return ""

"""好感度系统 — 5 阶段关系模型、变化规则、Prompt 注入"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar

logger = logging.getLogger(__name__)


# ── 5 阶段枚举 ──


class AffectionLevel(IntEnum):
    """好感度 5 阶段关系模型"""
    STRANGER = 1      # 陌生
    ACQUAINTANCE = 2  # 认识
    TRUST = 3         # 信赖
    INTIMATE = 4      # 亲密
    PARTNER = 5       # 伴侣

    @property
    def title(self) -> str:
        """阶段中文标题"""
        return _LEVEL_TITLES[self]

    @property
    def address(self) -> str:
        """此阶段诺艾尔对用户的称呼"""
        return _LEVEL_ADDRESSES[self]

    @property
    def behavior_instruction(self) -> str:
        """此阶段的行为指令（注入 Prompt）"""
        return _LEVEL_BEHAVIORS[self]

    @property
    def threshold(self) -> int:
        """当前等级的经验值门槛（达到此分数所需的经验值）"""
        return _LEVEL_THRESHOLDS[self]

    @property
    def next_threshold(self) -> int | None:
        """下一等级的经验值门槛，已是最高等级返回 None"""
        next_level_ord = self.value + 1
        if next_level_ord > AffectionLevel.PARTNER.value:
            return None
        return _LEVEL_THRESHOLDS[AffectionLevel(next_level_ord)]

    @classmethod
    def from_points(cls, points: int) -> AffectionLevel:
        """根据经验值计算当前等级"""
        level = cls.STRANGER
        for lvl in cls:
            if points >= lvl.threshold:
                level = lvl
            else:
                break
        return level


_LEVEL_TITLES: dict[AffectionLevel, str] = {
    AffectionLevel.STRANGER: "陌生",
    AffectionLevel.ACQUAINTANCE: "认识",
    AffectionLevel.TRUST: "信赖",
    AffectionLevel.INTIMATE: "亲密",
    AffectionLevel.PARTNER: "伴侣",
}

_LEVEL_ADDRESSES: dict[AffectionLevel, str] = {
    AffectionLevel.STRANGER: "你",
    AffectionLevel.ACQUAINTANCE: "你",
    AffectionLevel.TRUST: "你",
    AffectionLevel.INTIMATE: "你",
    AffectionLevel.PARTNER: "你",
}

_LEVEL_BEHAVIORS: dict[AffectionLevel, str] = {
    AffectionLevel.STRANGER: (
        "## 当前关系状态：陌生\n"
        "你们刚刚认识不久，还不太熟悉。诺艾尔保持礼貌但略显生疏的态度，"
        "用敬称「你」称呼对方，回答简洁有礼，不会主动展开话题。"
    ),
    AffectionLevel.ACQUAINTANCE: (
        "## 当前关系状态：认识\n"
        "你们已经有过一些交流，开始互相了解。诺艾尔的态度变得友善一些，"
        "会主动关心对方，偶尔会询问对方的近况，语气比之前温暖。"
    ),
    AffectionLevel.TRUST: (
        "## 当前关系状态：信赖\n"
        "你们已经建立了信任关系，诺艾尔把对方当作重要的人。"
        "她会主动分享自己的想法，关心对方的生活，语气亲近而真诚，"
        "会主动提出建议和帮助。"
    ),
    AffectionLevel.INTIMATE: (
        "## 当前关系状态：亲密\n"
        "你们的关系非常亲密，诺艾尔对对方有着深厚的感情。"
        "她会表现出依赖和撒娇的一面，语气温柔而亲昵，"
        "会主动表达思念和关心，偶尔会有一些暧昧的对话。"
    ),
    AffectionLevel.PARTNER: (
        "## 当前关系状态：伴侣\n"
        "你们已经是最亲密的关系，诺艾尔完全信任并依赖对方。"
        "她毫不掩饰自己的感情，会主动表达爱意，语气深情而温柔，"
        "把对方的幸福当作自己最重要的事。"
    ),
}

# 升级到该等级所需的累计经验值
_LEVEL_THRESHOLDS: dict[AffectionLevel, int] = {
    AffectionLevel.STRANGER: 0,
    AffectionLevel.ACQUAINTANCE: 100,
    AffectionLevel.TRUST: 300,
    AffectionLevel.INTIMATE: 600,
    AffectionLevel.PARTNER: 1000,
}


# ── 状态数据类 ──


@dataclass
class AffectionState:
    """单个用户的好感度状态"""
    user_id: int
    level: AffectionLevel
    points: int

    @classmethod
    def new(cls, user_id: int, initial_level: int = 1, initial_points: int = 0) -> AffectionState:
        """创建初始状态

        如果只提供 initial_points，等级会根据经验值自动计算。
        如果同时提供两者，以 initial_points 计算出的等级为准（经验值优先）。
        """
        level = AffectionLevel.from_points(initial_points)
        return cls(user_id=user_id, level=level, points=initial_points)

    def with_points(self, new_points: int) -> AffectionState:
        """返回更新经验值后的新状态（等级自动重算）"""
        new_level = AffectionLevel.from_points(new_points)
        return AffectionState(
            user_id=self.user_id,
            level=new_level,
            points=new_points,
        )


# ── 存储层 ──


class AffectionRepository(ABC):
    """好感度存储抽象"""

    @abstractmethod
    async def get(self, user_id: int) -> AffectionState | None:
        """获取用户好感度状态，不存在返回 None"""
        ...

    @abstractmethod
    async def save(self, state: AffectionState) -> None:
        """保存用户好感度状态"""
        ...

    @abstractmethod
    async def create_table(self) -> None:
        """创建好感度表（首次启动时调用）"""
        ...


class InMemoryAffectionRepository(AffectionRepository):
    """内存存储（用于测试和开发）"""

    def __init__(self) -> None:
        self._store: dict[int, AffectionState] = {}

    async def get(self, user_id: int) -> AffectionState | None:
        return self._store.get(user_id)

    async def save(self, state: AffectionState) -> None:
        self._store[state.user_id] = state

    async def create_table(self) -> None:
        pass  # 内存存储无需建表

    def clear(self) -> None:
        """测试辅助：清空所有数据"""
        self._store.clear()


class PostgresAffectionRepository(AffectionRepository):
    """PostgreSQL 存储（生产环境）"""

    # 建表 SQL
    CREATE_TABLE_SQL: ClassVar[str] = """
        CREATE TABLE IF NOT EXISTS affection (
            user_id     BIGINT PRIMARY KEY,
            level       INTEGER NOT NULL DEFAULT 1,
            points      INTEGER NOT NULL DEFAULT 0,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """

    def __init__(self, dsn: str) -> None:
        """
        Args:
            dsn: PostgreSQL 连接字符串，如 postgresql://user:pass@host:5432/dbname
        """
        self._dsn = dsn
        self._pool = None

    async def _get_pool(self):
        """懒加载连接池"""
        if self._pool is None:
            import asyncpg
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
        return self._pool

    async def create_table(self) -> None:
        """创建好感度表"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(self.CREATE_TABLE_SQL)
        logger.info("好感度表创建/确认完成")

    async def get(self, user_id: int) -> AffectionState | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT user_id, level, points FROM affection WHERE user_id = $1",
                user_id,
            )
        if row is None:
            return None
        return AffectionState(
            user_id=row["user_id"],
            level=AffectionLevel(row["level"]),
            points=row["points"],
        )

    async def save(self, state: AffectionState) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO affection (user_id, level, points, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (user_id) DO UPDATE
                    SET level = EXCLUDED.level,
                        points = EXCLUDED.points,
                        updated_at = NOW();
                """,
                state.user_id,
                state.level.value,
                state.points,
            )

    async def close(self) -> None:
        """关闭连接池"""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


# ── 变化规则 ──


# 正面关键词 → 经验值增减
# 按权重分组，避免单一消息暴涨
_POSITIVE_KEYWORDS: list[tuple[list[str], int]] = [
    # 高权重：明确表达好感
    (["喜欢你", "爱你", "想你", "最爱", "亲亲", "抱抱"], 15),
    (["可爱", "漂亮", "温柔", "体贴"], 10),
    # 中权重：关心和感谢
    (["谢谢", "感谢", "辛苦了", "帮了大忙"], 8),
    (["在干嘛", "吃了吗", "睡了吗", "还好吗", "身体"], 5),
    (["早安", "晚安", "晚安"], 5),
    # 低权重：友好互动
    (["哈哈", "不错", "好的", "嗯嗯"], 2),
]

_NEGATIVE_KEYWORDS: list[tuple[list[str], int]] = [
    (["烦死了", "滚", "讨厌你", "无聊"], -15),
    (["别烦", "闭嘴", "不想理你"], -10),
    (["不好", "不行", "算了"], -3),
]

# 单次消息经验值变化上限（防刷）
MAX_DELTA_PER_MESSAGE: int = 20
MIN_DELTA_PER_MESSAGE: int = -20


def analyze_message(message: str) -> int:
    """
    分析单条消息的好感度经验值变化。

    基于关键词匹配，返回经验值变化量（可正可负）。
    单次变化受 MAX_DELTA_PER_MESSAGE 限制。

    Args:
        message: 用户消息文本

    Returns:
        经验值变化量
    """
    if not message:
        return 0

    delta = 0
    message_lower = message.lower()

    # 正面关键词
    for keywords, weight in _POSITIVE_KEYWORDS:
        for kw in keywords:
            if kw in message_lower:
                delta += weight
                break  # 每组只计一次

    # 负面关键词
    for keywords, weight in _NEGATIVE_KEYWORDS:
        for kw in keywords:
            if kw in message_lower:
                delta += weight
                break

    # 限制单次变化幅度
    delta = max(MIN_DELTA_PER_MESSAGE, min(MAX_DELTA_PER_MESSAGE, delta))

    if delta != 0:
        logger.debug("好感度分析: message=%r, delta=%d", message[:30], delta)

    return delta


# ── 阶段变化处理 ──


# 升级时的过渡对话提示（注入到对话上下文中）
_TRANSITION_MESSAGES: dict[AffectionLevel, str] = {
    AffectionLevel.ACQUAINTANCE: (
        "（诺艾尔开始对你有些好感了，说话的语气变得柔和了一些。）"
    ),
    AffectionLevel.TRUST: (
        "（诺艾尔已经把你当作重要的人，眼神中多了一份信赖。）"
    ),
    AffectionLevel.INTIMATE: (
        "（诺艾尔对你的感情越来越深，不自觉地想要靠近你。）"
    ),
    AffectionLevel.PARTNER: (
        "（诺艾尔已经认定你是她最重要的人，心中满是爱意。）"
    ),
}


def get_transition_message(old_level: AffectionLevel, new_level: AffectionLevel) -> str | None:
    """
    获取等级变化时的过渡对话提示。

    Args:
        old_level: 变化前的等级
        new_level: 变化后的等级

    Returns:
        过渡对话文本，未升级返回 None
    """
    if new_level <= old_level:
        return None
    return _TRANSITION_MESSAGES.get(new_level)


# ── 好感度系统主类 ──


class AffectionSystem:
    """
    好感度系统主类。

    用法：
        repo = InMemoryAffectionRepository()
        system = AffectionSystem(repo, initial_level=1, initial_points=0)
        result = await system.process_message(user_id=123, message="你好")
        # result.new_state, result.points_delta, result.transition_message
    """

    @dataclass
    class Result:
        """处理结果"""
        user_id: int
        old_state: AffectionState | None
        new_state: AffectionState
        points_delta: int
        level_changed: bool
        transition_message: str | None = None

    def __init__(
        self,
        repository: AffectionRepository,
        initial_level: int = 1,
        initial_points: int = 0,
    ) -> None:
        self._repo = repository
        self._initial_level = initial_level
        self._initial_points = initial_points

    async def get_state(self, user_id: int) -> AffectionState:
        """获取用户状态，不存在则创建初始状态"""
        state = await self._repo.get(user_id)
        if state is None:
            state = AffectionState.new(user_id, self._initial_level, self._initial_points)
            await self._repo.save(state)
        return state

    async def process_message(self, user_id: int, message: str) -> Result:
        """
        处理用户消息，更新好感度。

        Args:
            user_id: 用户 ID
            message: 用户消息

        Returns:
            Result 包含变化详情
        """
        old_state = await self.get_state(user_id)
        delta = analyze_message(message)
        new_points = max(0, old_state.points + delta)  # 经验值不低于 0
        new_state = old_state.with_points(new_points)

        level_changed = new_state.level != old_state.level
        transition = get_transition_message(old_state.level, new_state.level) if level_changed else None

        await self._repo.save(new_state)

        if level_changed:
            logger.info(
                "好感度升级: user_id=%d, %s → %s (%d pts)",
                user_id, old_state.level.title, new_state.level.title, new_points,
            )
        elif delta != 0:
            logger.debug(
                "好感度变化: user_id=%d, delta=%d, total=%d",
                user_id, delta, new_points,
            )

        return self.Result(
            user_id=user_id,
            old_state=old_state,
            new_state=new_state,
            points_delta=delta,
            level_changed=level_changed,
            transition_message=transition,
        )

    def get_prompt_layer(self, state: AffectionState) -> str:
        """
        生成好感度 Prompt 层（Layer 2）。

        Args:
            state: 当前好感度状态

        Returns:
            注入到 system prompt 的文本
        """
        return build_affection_prompt_layer(state)


def build_affection_prompt_layer(state: AffectionState) -> str:
    """
    生成好感度 Prompt 层（Layer 2）。

    独立函数，无需 AffectionSystem 实例即可调用。

    Args:
        state: 当前好感度状态

    Returns:
        注入到 system prompt 的文本
    """
    if state.level.next_threshold is not None:
        progress = f"{state.points}/{state.level.next_threshold}"
    else:
        progress = f"{state.points}/∞"
    return (
        f"## 好感度状态\n"
        f"当前关系阶段：{state.level.title}（{state.level.address}）\n"
        f"亲密度经验值：{progress}\n\n"
        f"{state.level.behavior_instruction}"
    )

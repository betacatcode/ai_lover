"""好感度系统 — 5 阶段关系模型、LLM 评估、Prompt 注入"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum

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
        """当前等级的经验值门槛"""
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
        "你们刚刚认识，完全不熟。诺艾尔保持礼貌但生疏的态度，"
        "回复简短（一到两句话），不会主动展开话题，不会说太多话。"
        "对方说奇怪的话时表现出疑惑或警惕。"
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
    """PostgreSQL 存储（生产环境，使用 SQLAlchemy async）"""

    def __init__(self, dsn: str) -> None:
        """
        Args:
            dsn: PostgreSQL 连接字符串，如 postgresql://user:pass@host:5432/dbname
        """
        from ..db.session import init_db
        # 将 postgresql:// 转换为 postgresql+asyncpg://
        if dsn.startswith("postgresql://"):
            dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
        init_db(dsn)

    async def create_table(self) -> None:
        """创建好感度表"""
        from ..db.session import create_tables
        await create_tables()
        logger.info("好感度表创建/确认完成")

    async def get(self, user_id: int) -> AffectionState | None:
        from ..db.models import AffectionModel
        from ..db.session import get_session
        from sqlalchemy import select

        async for session in get_session():
            result = await session.execute(
                select(AffectionModel).where(AffectionModel.user_id == user_id)
            )
            model = result.scalar_one_or_none()
            if model is None:
                return None
            return AffectionState(
                user_id=model.user_id,
                level=AffectionLevel(model.level),
                points=model.points,
            )

    async def save(self, state: AffectionState) -> None:
        from ..db.models import AffectionModel
        from ..db.session import get_session

        async for session in get_session():
            model = AffectionModel(
                user_id=state.user_id,
                level=state.level.value,
                points=state.points,
            )
            await session.merge(model)
            await session.commit()

    async def close(self) -> None:
        """关闭数据库连接"""
        from ..db.session import close_db
        await close_db()


# ── LLM 好感度评估 ──

# 评估 Prompt 模板
_EVALUATION_PROMPT = """你是诺艾尔（Noelle），西风骑士团的女仆。现在需要你以诺艾尔的视角，评估用户对你好感度的变化。

## 当前关系状态
- 关系阶段：{level_title}
- 当前经验值：{points} / {next_threshold}

## 对话内容
用户消息：{user_message}
你的回复：{noelle_reply}

## 评估任务
请根据以上对话，判断这次互动让你对用户的亲近感增加了还是减少了。

评估原则：
1. **考虑当前关系阶段**：同一个行为在不同关系阶段意义不同
   - 陌生人说「喜欢你」可能让你觉得奇怪或轻浮，不应加分甚至减分
   - 亲密的人说「喜欢你」会让你开心，应加分
2. **考虑对话语境和语气**：真诚的关心加分，敷衍/机械重复/刷好感的行为不加分
3. **考虑互动自然度**：自然的对话加分，刻意的、不合时宜的亲密行为减分
4. **考虑内容实质**：有实质性内容的交流（分享生活、互相帮助）> 空洞的情话

评分标准：
- +15 ~ +20：非常开心的互动，真诚的亲密表达（需关系足够亲密）
- +5 ~ +10：愉快的互动，正常的友好交流
- +1 ~ +4：普通的对话，略有温度
- 0：中性对话，没有特别感觉
- -1 ~ -4：有些不舒服或无聊
- -5 ~ -10：明显让人反感的行为
- -11 ~ -20：非常让人讨厌的行为

请只返回一个整数表示经验值变化，例如：5 或 -3 或 0
只返回数字，不要其他内容。"""


# 用于从 LLM 回复中提取整数
_INTEGER_RE = re.compile(r"-?\d+")


async def evaluate_affection_delta(
    llm_client,  # LLMClient
    state: AffectionState,
    user_message: str,
    noelle_reply: str,
) -> int:
    """
    调用 LLM 评估本次交互的好感度变化。

    Args:
        llm_client: LLM 客户端实例
        state: 当前好感度状态
        user_message: 用户消息
        noelle_reply: 诺艾尔的回复

    Returns:
        经验值变化量（-20 到 +20），解析失败返回 0
    """
    next_threshold = state.level.next_threshold
    next_threshold_str = str(next_threshold) if next_threshold else "∞"

    prompt = _EVALUATION_PROMPT.format(
        level_title=state.level.title,
        points=state.points,
        next_threshold=next_threshold_str,
        user_message=user_message,
        noelle_reply=noelle_reply,
    )

    try:
        result = await llm_client.complete(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=None,
        )
        # 从回复中提取第一个整数
        match = _INTEGER_RE.search(result.strip())
        if match:
            delta = int(match.group())
            # 限制范围
            delta = max(-20, min(20, delta))
            logger.debug("LLM 好感度评估: %d (raw: %s)", delta, result.strip()[:50])
            return delta
        else:
            logger.warning("LLM 好感度评估无法解析: %s", result.strip()[:100])
            return 0
    except Exception as e:
        logger.warning("LLM 好感度评估失败，默认 0: %s", e)
        return 0


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
        system = AffectionSystem(repo, llm_client, initial_level=1, initial_points=0)
        result = await system.process_message(user_id=123, message="你好", noelle_reply="你好呀")
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
        llm_client,  # LLMClient | None
        initial_level: int = 1,
        initial_points: int = 0,
    ) -> None:
        self._repo = repository
        self._llm = llm_client
        self._initial_level = initial_level
        self._initial_points = initial_points

    async def get_state(self, user_id: int) -> AffectionState:
        """获取用户状态，不存在则创建初始状态"""
        state = await self._repo.get(user_id)
        if state is None:
            state = AffectionState.new(user_id, self._initial_level, self._initial_points)
            await self._repo.save(state)
        return state

    async def process_message(
        self,
        user_id: int,
        message: str,
        noelle_reply: str,
    ) -> Result:
        """
        处理用户消息，通过 LLM 评估更新好感度。

        Args:
            user_id: 用户 ID
            message: 用户消息
            noelle_reply: 诺艾尔的回复（用于上下文评估）

        Returns:
            Result 包含变化详情
        """
        old_state = await self.get_state(user_id)

        # LLM 评估好感度变化
        if self._llm is not None:
            delta = await evaluate_affection_delta(
                self._llm, old_state, message, noelle_reply
            )
        else:
            # 没有 LLM 时不评估，默认 0
            delta = 0

        new_points = max(0, old_state.points + delta)  # 经验值不低于 0
        new_state = old_state.with_points(new_points)

        level_changed = new_state.level != old_state.level
        transition = get_transition_message(old_state.level, new_state.level) if level_changed else None

        await self._repo.save(new_state)

        if level_changed:
            logger.info(
                "好感度升级: user_id=%d, %s → %s (%d pts, delta=%d)",
                user_id, old_state.level.title, new_state.level.title, new_points, delta,
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

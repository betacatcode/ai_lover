"""情绪系统 — 6 种情绪状态、LLM 触发、自然衰减、Prompt 注入"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ── 6 种情绪枚举 ──


class EmotionType(str, Enum):
    """6 种情绪状态"""
    HAPPY = "开心"
    WORRIED = "担心"
    LONELY = "寂寞"
    SAD = "难过"
    ANGRY = "生气"
    CALM = "平静"


# 所有非平静情绪（会被衰减）
_EMOTIONS_TO_DECAY: set[EmotionType] = {
    EmotionType.HAPPY,
    EmotionType.WORRIED,
    EmotionType.LONELY,
    EmotionType.SAD,
    EmotionType.ANGRY,
}

# 默认初始强度
_DEFAULT_INTENSITIES: dict[EmotionType, int] = {
    EmotionType.HAPPY: 0,
    EmotionType.WORRIED: 0,
    EmotionType.LONELY: 0,
    EmotionType.SAD: 0,
    EmotionType.ANGRY: 0,
    EmotionType.CALM: 0,
}


# ── Emoji 映射（debug 显示用）──

_EMOTION_EMOJI: dict[EmotionType, str] = {
    EmotionType.HAPPY: "😊",
    EmotionType.WORRIED: "😟",
    EmotionType.LONELY: "🥺",
    EmotionType.SAD: "😢",
    EmotionType.ANGRY: "😤",
    EmotionType.CALM: "😌",
}

# 好感度对应爱心颜色
_AFFECTION_HEART: dict[int, str] = {
    1: "🤍",  # 陌生
    2: "💙",  # 认识
    3: "💛",  # 信赖
    4: "🧡",  # 亲密
    5: "❤️",  # 伴侣
}


# ── 语气风格指令（注入 Prompt Layer 3）──

_EMOTION_PROMPT_LAYERS: dict[EmotionType, str] = {
    EmotionType.HAPPY: (
        "## 当前情绪：开心\n"
        "诺艾尔现在心情很好！回复时语气轻快活泼，"
        "可能会主动分享一些有趣的事，或者用轻松的话题延续对话。"
    ),
    EmotionType.WORRIED: (
        "## 当前情绪：担心\n"
        "诺艾尔很担心用户！回复时语气温柔关切，"
        "会主动询问用户的状况，表达关心和安慰。"
    ),
    EmotionType.LONELY: (
        "## 当前情绪：寂寞\n"
        "诺艾尔感到有些孤单……回复时会小心翼翼，"
        "可能主动找话题，或者用略带不安的语气询问对方在不在。"
    ),
    EmotionType.SAD: (
        "## 当前情绪：难过\n"
        "诺艾尔现在有点难过，但她会强装坚强。"
        "回复时可能说'诺艾尔没事的'，语气低落但努力维持正常。"
    ),
    EmotionType.ANGRY: (
        "## 当前情绪：生气\n"
        "诺艾尔现在有点生气！回复时傲娇，"
        "会说'诺艾尔才没有生气呢！'之类的反话，语气带刺但不过分。"
    ),
    EmotionType.CALM: (
        "## 当前情绪：平静\n"
        "诺艾尔现在心情平静，回复自然，无特殊情绪色彩。"
    ),
}


# ── 情绪变化事件 ──


@dataclass
class EmotionEvent:
    """LLM 检测到的一次情绪变化"""
    emotion: EmotionType      # 哪种情绪
    delta: int                # 变化量（正数增加，负数减少）
    reason: str = ""          # 原因（调试用）

    @classmethod
    def from_dict(cls, data: dict) -> EmotionEvent | None:
        """从 LLM 返回的字典解析"""
        try:
            emotion_str = data.get("emotion", "")
            emotion = _EMOTION_TYPE_BY_VALUE.get(emotion_str)
            if emotion is None:
                return None
            delta = int(data.get("delta", 0))
            reason = data.get("reason", "")
            return cls(emotion=emotion, delta=delta, reason=reason)
        except (ValueError, TypeError):
            return None


# 反向查找：中文值 → 枚举
_EMOTION_TYPE_BY_VALUE: dict[str, EmotionType] = {
    e.value: e for e in EmotionType
}


# ── 情绪状态数据类 ──


@dataclass
class EmotionState:
    """
    单个用户的情绪状态。

    6 种情绪各有强度值（0+），当前情绪取强度最大的那个。
    全为 0 时视为平静。
    强度相同时，最近触发的情绪优先（last_triggered 记录）。

    cooldown_rounds: 剩余冷却轮数，>0 时 LLM 触发的情绪变化会被抑制（幅度减半）
    """
    user_id: int
    intensities: dict[EmotionType, int] = field(default_factory=lambda: dict(_DEFAULT_INTENSITIES))
    cooldown_rounds: int = 0  # 情绪切换冷却轮数
    last_triggered: EmotionType | None = None  # 最近被触发的情绪（用于平局决胜）

    @classmethod
    def new(cls, user_id: int) -> EmotionState:
        """创建初始状态（全 0，即平静）"""
        return cls(user_id=user_id, intensities=dict(_DEFAULT_INTENSITIES), cooldown_rounds=0, last_triggered=None)

    @property
    def current_emotion(self) -> EmotionType:
        """当前情绪 = 强度最大的那个。全 0 返回平静。强度相同时，最近触发的优先。"""
        max_intensity = max(self.intensities.values())
        if max_intensity <= 0:
            return EmotionType.CALM
        # 找出所有达到最大强度的情绪
        candidates = [
            e for e in EmotionType
            if self.intensities.get(e, 0) == max_intensity
        ]
        # 如果有多个，优先返回最近触发的那个
        if len(candidates) > 1 and self.last_triggered in candidates:
            return self.last_triggered
        return candidates[0]

    @property
    def current_intensity(self) -> int:
        """当前情绪的强度值"""
        return self.intensities.get(self.current_emotion, 0)

    def apply_event(self, event: EmotionEvent) -> None:
        """应用一次情绪变化事件"""
        # 冷却期：如果目标情绪与当前情绪不同，抑制变化幅度
        effective_delta = event.delta
        if self.cooldown_rounds > 0 and event.emotion != self.current_emotion:
            effective_delta = event.delta // 2  # 幅度减半
            if effective_delta == 0:
                effective_delta = 1 if event.delta > 0 else -1
            logger.debug("情绪冷却中: %s %+d → %+d", event.emotion.value, event.delta, effective_delta)

        current = self.intensities.get(event.emotion, 0)
        new_value = max(0, current + effective_delta)  # 不低于 0
        self.intensities[event.emotion] = new_value

        # 记录最近触发的情绪（用于平局决胜）
        if effective_delta != 0:
            self.last_triggered = event.emotion

        # 如果情绪实际切换了，进入冷却期
        if event.emotion == self.current_emotion and abs(event.delta) >= 2:
            self.cooldown_rounds = 2  # 2 轮冷却

        logger.debug(
            "情绪变化: %s %s%d → %d (%s)",
            event.emotion.value,
            "+" if effective_delta >= 0 else "",
            effective_delta,
            new_value,
            event.reason[:30] if event.reason else "",
        )

    def tick_cooldown(self) -> None:
        """每轮对话后递减冷却"""
        if self.cooldown_rounds > 0:
            self.cooldown_rounds -= 1

    def decay(self, amount: int = 1) -> None:
        """衰减所有非平静情绪"""
        for emotion in _EMOTIONS_TO_DECAY:
            current = self.intensities.get(emotion, 0)
            if current > 0:
                self.intensities[emotion] = max(0, current - amount)

    @property
    def emoji(self) -> str:
        """当前情绪对应的 emoji"""
        return _EMOTION_EMOJI.get(self.current_emotion, "😌")

    def get_prompt_layer(self) -> str:
        """获取当前情绪的 Prompt 注入文本"""
        return _EMOTION_PROMPT_LAYERS.get(
            self.current_emotion,
            _EMOTION_PROMPT_LAYERS[EmotionType.CALM],
        )


# ── 存储层 ──


class EmotionRepository(ABC):
    """情绪存储抽象"""

    @abstractmethod
    async def get(self, user_id: int) -> EmotionState | None:
        ...

    @abstractmethod
    async def save(self, state: EmotionState) -> None:
        ...


class InMemoryEmotionRepository(EmotionRepository):
    """内存存储（用于测试和开发）"""

    def __init__(self) -> None:
        self._store: dict[int, EmotionState] = {}

    async def get(self, user_id: int) -> EmotionState | None:
        return self._store.get(user_id)

    async def save(self, state: EmotionState) -> None:
        self._store[state.user_id] = state

    async def get_all_user_ids(self) -> list[int]:
        """获取所有用户 ID"""
        return list(self._store.keys())

    def clear(self) -> None:
        self._store.clear()


class PostgresEmotionRepository(EmotionRepository):
    """PostgreSQL 存储（生产环境）"""

    def __init__(self, dsn: str) -> None:
        from ..db.session import init_db
        if dsn.startswith("postgresql://"):
            dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
        init_db(dsn)

    async def get(self, user_id: int) -> EmotionState | None:
        from ..db.models import EmotionModel
        from ..db.session import get_session
        from sqlalchemy import select

        async for session in get_session():
            result = await session.execute(
                select(EmotionModel).where(EmotionModel.user_id == user_id)
            )
            model = result.scalar_one_or_none()
            if model is None:
                return None
            return EmotionState(
                user_id=model.user_id,
                intensities={
                    EmotionType.HAPPY: model.happy,
                    EmotionType.WORRIED: model.worried,
                    EmotionType.LONELY: model.lonely,
                    EmotionType.SAD: model.sad,
                    EmotionType.ANGRY: model.angry,
                    EmotionType.CALM: 0,
                },
            )

    async def save(self, state: EmotionState) -> None:
        from ..db.models import EmotionModel
        from ..db.session import get_session

        async for session in get_session():
            model = EmotionModel(
                user_id=state.user_id,
                happy=state.intensities.get(EmotionType.HAPPY, 0),
                worried=state.intensities.get(EmotionType.WORRIED, 0),
                lonely=state.intensities.get(EmotionType.LONELY, 0),
                sad=state.intensities.get(EmotionType.SAD, 0),
                angry=state.intensities.get(EmotionType.ANGRY, 0),
            )
            await session.merge(model)
            await session.commit()

    async def create_table(self) -> None:
        """创建情绪表"""
        from ..db.session import create_tables
        await create_tables()
        logger.info("情绪表创建/确认完成")


# ── LLM 情绪评估 ──


_EVALUATION_PROMPT = """你是诺艾尔（Noelle），西风骑士团的女仆。现在需要你以诺艾尔的视角，评估对话对你的情绪影响。

## 当前情绪状态（0=无，数字越大越强烈）
- 开心：{happy}
- 担心：{worried}
- 寂寞：{lonely}
- 难过：{sad}
- 生气：{angry}

## 对话内容
用户消息：{user_message}
你的回复：{noelle_reply}

## 评估任务
请判断用户这次消息让你产生了什么情绪变化。

## 触发规则（严格遵守）

### 让用户开心（必须真正正面才触发）：
- 真诚夸奖/感谢 → 开心 +1~2
- 分享开心的事（升职、约会成功等）→ 开心 +1
- 主动关心诺艾尔 → 开心 +1

### 让用户担心：
- 用户说身体不舒服/生病 → 担心 +2
- 用户表达焦虑/压力大 → 担心 +1
- 用户遇到困难 → 担心 +1

### 让用户生气（粗鲁/冒犯必触发）：
- 骂人/说脏话 → 生气 +2~3
- 傲慢/轻视（"我是你爹""滚""烦死了"）→ 生气 +2
- 反复无视诺艾尔 → 生气 +1
- 不尊重/调侃 → 生气 +1

### 让用户难过：
- 用户说讨厌诺艾尔/不想聊天 → 难过 +2
- 用户长期不回复 → 难过 +1

### 让用户寂寞：
- 用户很久没发消息（根据上下文判断）→ 寂寞 +1

## 重要原则
1. **粗鲁/冒犯必须触发生气**，不要忍让！诺艾尔虽然礼貌但不是软柿子
2. **普通对话不要变情绪**：打招呼、闲聊、问问题等日常对话 → 返回 delta=0
3. **只返回最有影响力的那个情绪变化**，不要一次变多个
4. **考虑当前情绪强度**：如果某种情绪已经很高，再叠加时增幅减小

## 变化幅度
- +3：极其强烈（严重辱骂、大病、告白）
- +2：明显事件（被骂、升职、失恋、被忽视）
- +1：轻微波动（普通关心、普通分享）
- 0：日常对话，无情绪变化

请返回 JSON 格式：
```json
{{"emotion": "开心|担心|寂寞|难过|生气", "delta": 数字, "reason": "20字以内原因"}}
```

只返回 JSON，不要其他内容。"""


_JSON_RE = re.compile(r"\{[^{}]*\}")


async def evaluate_emotion_events(
    llm_client,  # LLMClient
    state: EmotionState,
    user_message: str,
    noelle_reply: str,
) -> list[EmotionEvent]:
    """
    调用 LLM 评估本次交互的情绪变化。

    Args:
        llm_client: LLM 客户端实例
        state: 当前情绪状态
        user_message: 用户消息
        noelle_reply: 诺艾尔的回复

    Returns:
        情绪变化事件列表（通常 0-2 个）
    """
    prompt = _EVALUATION_PROMPT.format(
        happy=state.intensities.get(EmotionType.HAPPY, 0),
        worried=state.intensities.get(EmotionType.WORRIED, 0),
        lonely=state.intensities.get(EmotionType.LONELY, 0),
        sad=state.intensities.get(EmotionType.SAD, 0),
        angry=state.intensities.get(EmotionType.ANGRY, 0),
        user_message=user_message,
        noelle_reply=noelle_reply,
    )

    try:
        result = await llm_client.complete(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=None,
        )
        # 解析 JSON
        match = _JSON_RE.search(result.strip())
        if match:
            import json
            data = json.loads(match.group())
            event = EmotionEvent.from_dict(data)
            if event is not None and event.delta != 0:
                logger.debug("LLM 情绪评估: %s %+d (%s)", event.emotion.value, event.delta, event.reason[:30])
                return [event]
        logger.debug("LLM 情绪评估: 无变化 (raw: %s)", result.strip()[:100])
        return []
    except Exception as e:
        logger.warning("LLM 情绪评估失败: %s", e)
        return []


# ── 情绪系统主类 ──


class EmotionSystem:
    """
    情绪系统主类。

    用法：
        repo = InMemoryEmotionRepository()
        system = EmotionSystem(repo, llm_client)
        result = await system.process_message(user_id=123, message="你好", noelle_reply="你好呀")
    """

    @dataclass
    class Result:
        """处理结果"""
        user_id: int
        old_emotion: EmotionType
        new_emotion: EmotionType
        events: list[EmotionEvent]
        state: EmotionState

    def __init__(
        self,
        repository: EmotionRepository,
        llm_client,  # LLMClient | None
        decay_interval_minutes: int = 30,
        decay_amount: int = 1,
    ) -> None:
        self._repo = repository
        self._llm = llm_client
        self._decay_interval = decay_interval_minutes
        self._decay_amount = decay_amount

    async def get_state(self, user_id: int) -> EmotionState:
        """获取用户状态，不存在则创建初始状态"""
        state = await self._repo.get(user_id)
        if state is None:
            state = EmotionState.new(user_id)
            await self._repo.save(state)
        return state

    async def process_message(
        self,
        user_id: int,
        message: str,
        noelle_reply: str,
    ) -> Result:
        """
        处理用户消息，通过 LLM 评估更新情绪。

        Args:
            user_id: 用户 ID
            message: 用户消息
            noelle_reply: 诺艾尔的回复

        Returns:
            Result 包含变化详情
        """
        state = await self.get_state(user_id)
        old_emotion = state.current_emotion

        # LLM 评估情绪变化
        events: list[EmotionEvent] = []
        if self._llm is not None:
            events = await evaluate_emotion_events(
                self._llm, state, message, noelle_reply
            )
            for event in events:
                state.apply_event(event)

        await self._repo.save(state)

        if events:
            logger.info(
                "情绪变化: user_id=%d, %s → %s, events=%d",
                user_id, old_emotion.value, state.current_emotion.value, len(events),
            )

        return self.Result(
            user_id=user_id,
            old_emotion=old_emotion,
            new_emotion=state.current_emotion,
            events=events,
            state=state,
        )

    async def apply_decay(self, user_id: int) -> None:
        """对单个用户应用情绪衰减"""
        state = await self._repo.get(user_id)
        if state is None:
            return
        old_emotion = state.current_emotion
        state.decay(self._decay_amount)
        await self._repo.save(state)
        if old_emotion != state.current_emotion:
            logger.info(
                "情绪衰减: user_id=%d, %s → %s",
                user_id, old_emotion.value, state.current_emotion.value,
            )

    def get_prompt_layer(self, state: EmotionState) -> str:
        """
        生成情绪 Prompt 层（Layer 3）。

        Args:
            state: 当前情绪状态

        Returns:
            注入到 system prompt 的文本
        """
        return state.get_prompt_layer()

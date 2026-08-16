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
    """
    user_id: int
    intensities: dict[EmotionType, int] = field(default_factory=lambda: dict(_DEFAULT_INTENSITIES))

    @classmethod
    def new(cls, user_id: int) -> EmotionState:
        """创建初始状态（全 0，即平静）"""
        return cls(user_id=user_id, intensities=dict(_DEFAULT_INTENSITIES))

    @property
    def current_emotion(self) -> EmotionType:
        """当前情绪 = 强度最大的那个。全 0 返回平静"""
        max_intensity = max(self.intensities.values())
        if max_intensity <= 0:
            return EmotionType.CALM
        # 取第一个最大强度的情绪（避免随机）
        for emotion in EmotionType:
            if self.intensities.get(emotion, 0) == max_intensity:
                return emotion
        return EmotionType.CALM

    @property
    def current_intensity(self) -> int:
        """当前情绪的强度值"""
        return self.intensities.get(self.current_emotion, 0)

    def apply_event(self, event: EmotionEvent) -> None:
        """应用一次情绪变化事件"""
        current = self.intensities.get(event.emotion, 0)
        new_value = max(0, current + event.delta)  # 不低于 0
        self.intensities[event.emotion] = new_value
        logger.debug(
            "情绪变化: %s %s%d → %d (%s)",
            event.emotion.value,
            "+" if event.delta >= 0 else "",
            event.delta,
            new_value,
            event.reason[:30] if event.reason else "",
        )

    def decay(self, amount: int = 1) -> None:
        """衰减所有非平静情绪"""
        for emotion in _EMOTIONS_TO_DECAY:
            current = self.intensities.get(emotion, 0)
            if current > 0:
                self.intensities[emotion] = max(0, current - amount)

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


# ── LLM 情绪评估 ──


_EVALUATION_PROMPT = """你是诺艾尔（Noelle），西风骑士团的女仆。现在需要你以诺艾尔的视角，评估对话对你的情绪影响。

## 当前情绪状态
- 开心：{happy}
- 担心：{worried}
- 寂寞：{lonely}
- 难过：{sad}
- 生气：{angry}

## 对话内容
用户消息：{user_message}
你的回复：{noelle_reply}

## 评估任务
请根据以上对话，判断这次互动让你的哪种情绪发生了变化。

评估原则：
1. **考虑对话语境和语气**：真诚的关心让你开心，敷衍/粗鲁让你生气或难过
2. **考虑情绪合理性**：
   - 用户分享开心的事 → 开心增加
   - 用户表达难过/生病 → 担心增加
   - 用户粗鲁/骂人 → 生气增加
   - 用户很久不回复 → 寂寞增加
   - 用户无视你的主动分享 → 难过增加
3. **考虑关系阶段**：同样的行为在不同关系阶段情绪反应不同
4. **不要过度反应**：普通对话不一定每次都要变情绪

变化幅度：
- +3：非常强烈的刺激（大病、严重表白、严重辱骂）
- +2：明显的正面/负面事件（升职、失恋、被夸、被忽视）
- +1：轻微的情绪波动（普通关心、普通分享）
- 0：无变化

请返回 JSON 格式：
```json
{{"emotion": "开心|担心|寂寞|难过|生气", "delta": 数字, "reason": "简短原因"}}
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

"""情绪系统单元测试"""

from __future__ import annotations

import pytest

from src.systems.emotion import (
    EmotionEvent,
    EmotionState,
    EmotionType,
    InMemoryEmotionRepository,
)


class TestEmotionState:
    """EmotionState 数据类测试"""

    def test_new_state_is_all_calm(self):
        """新创建的状态全为 0，当前情绪是平静"""
        state = EmotionState.new(user_id=123)
        assert state.current_emotion == EmotionType.CALM
        assert state.current_intensity == 0
        for emotion in EmotionType:
            assert state.intensities.get(emotion, 0) == 0

    def test_apply_event_increases_intensity(self):
        """应用事件增加对应情绪强度"""
        state = EmotionState.new(user_id=1)
        event = EmotionEvent(emotion=EmotionType.HAPPY, delta=2, reason="用户夸奖")
        state.apply_event(event)
        assert state.intensities[EmotionType.HAPPY] == 2
        assert state.current_emotion == EmotionType.HAPPY

    def test_apply_event_decreases_intensity(self):
        """应用事件减少对应情绪强度"""
        state = EmotionState.new(user_id=1)
        state.intensities[EmotionType.ANGRY] = 5
        event = EmotionEvent(emotion=EmotionType.ANGRY, delta=-2, reason="冷静了")
        state.apply_event(event)
        assert state.intensities[EmotionType.ANGRY] == 3

    def test_intensity_never_below_zero(self):
        """情绪强度不会低于 0"""
        state = EmotionState.new(user_id=1)
        event = EmotionEvent(emotion=EmotionType.SAD, delta=-5)
        state.apply_event(event)
        assert state.intensities[EmotionType.SAD] == 0

    def test_current_emotion_is_max_intensity(self):
        """当前情绪是强度最大的那个"""
        state = EmotionState.new(user_id=1)
        state.intensities[EmotionType.HAPPY] = 3
        state.intensities[EmotionType.WORRIED] = 1
        assert state.current_emotion == EmotionType.HAPPY

    def test_decay_reduces_all_emotions(self):
        """衰减降低所有非平静情绪"""
        state = EmotionState.new(user_id=1)
        state.intensities[EmotionType.HAPPY] = 3
        state.intensities[EmotionType.SAD] = 2
        state.decay(amount=1)
        assert state.intensities[EmotionType.HAPPY] == 2
        assert state.intensities[EmotionType.SAD] == 1

    def test_decay_to_calm(self):
        """衰减到 0 后回到平静"""
        state = EmotionState.new(user_id=1)
        state.intensities[EmotionType.HAPPY] = 1
        state.decay(amount=1)
        assert state.current_emotion == EmotionType.CALM

    def test_decay_does_not_go_negative(self):
        """衰减不会产生负值"""
        state = EmotionState.new(user_id=1)
        state.intensities[EmotionType.LONELY] = 1
        state.decay(amount=5)
        assert state.intensities[EmotionType.LONELY] == 0

    def test_get_prompt_layer_returns_instruction(self):
        """获取 Prompt 层返回语气指令"""
        state = EmotionState.new(user_id=1)
        state.intensities[EmotionType.HAPPY] = 3
        prompt = state.get_prompt_layer()
        assert "开心" in prompt

    def test_prompt_layer_for_calm(self):
        """平静时返回平静指令"""
        state = EmotionState.new(user_id=1)
        prompt = state.get_prompt_layer()
        assert "平静" in prompt


class TestEmotionEvent:
    """EmotionEvent 解析测试"""

    def test_from_dict_valid(self):
        """从有效字典解析"""
        data = {"emotion": "开心", "delta": 2, "reason": "被夸了"}
        event = EmotionEvent.from_dict(data)
        assert event is not None
        assert event.emotion == EmotionType.HAPPY
        assert event.delta == 2
        assert event.reason == "被夸了"

    def test_from_dict_invalid_emotion(self):
        """无效情绪返回 None"""
        data = {"emotion": "不存在", "delta": 1}
        event = EmotionEvent.from_dict(data)
        assert event is None

    def test_from_dict_missing_fields(self):
        """缺少字段返回 None"""
        event = EmotionEvent.from_dict({})
        assert event is None


class TestInMemoryEmotionRepository:
    """内存存储测试"""

    @pytest.mark.asyncio
    async def test_save_and_get(self):
        """保存后能正确读取"""
        repo = InMemoryEmotionRepository()
        state = EmotionState.new(user_id=42)
        state.intensities[EmotionType.HAPPY] = 5
        await repo.save(state)

        loaded = await repo.get(42)
        assert loaded is not None
        assert loaded.user_id == 42
        assert loaded.intensities[EmotionType.HAPPY] == 5

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self):
        """获取不存在的用户返回 None"""
        repo = InMemoryEmotionRepository()
        result = await repo.get(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_user_ids(self):
        """获取所有用户 ID"""
        repo = InMemoryEmotionRepository()
        await repo.save(EmotionState.new(user_id=1))
        await repo.save(EmotionState.new(user_id=2))
        ids = await repo.get_all_user_ids()
        assert set(ids) == {1, 2}

    @pytest.mark.asyncio
    async def test_clear(self):
        """清空所有数据"""
        repo = InMemoryEmotionRepository()
        await repo.save(EmotionState.new(user_id=1))
        repo.clear()
        assert await repo.get(1) is None

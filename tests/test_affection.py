"""好感度系统单元测试 — 覆盖数据模型、LLM 评估、Prompt 注入、阶段转换"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.systems.affection import (
    AffectionLevel,
    AffectionState,
    AffectionSystem,
    InMemoryAffectionRepository,
    build_affection_prompt_layer,
    evaluate_affection_delta,
    get_transition_message,
)


# ── AffectionLevel 枚举测试 ──


class TestAffectionLevel:
    """好感度等级枚举测试"""

    def test_enum_values(self):
        """枚举值应为 1-5"""
        assert AffectionLevel.STRANGER.value == 1
        assert AffectionLevel.ACQUAINTANCE.value == 2
        assert AffectionLevel.TRUST.value == 3
        assert AffectionLevel.INTIMATE.value == 4
        assert AffectionLevel.PARTNER.value == 5

    def test_titles(self):
        """各等级中文标题"""
        assert AffectionLevel.STRANGER.title == "陌生"
        assert AffectionLevel.ACQUAINTANCE.title == "认识"
        assert AffectionLevel.TRUST.title == "信赖"
        assert AffectionLevel.INTIMATE.title == "亲密"
        assert AffectionLevel.PARTNER.title == "伴侣"

    def test_thresholds(self):
        """升级阈值递增"""
        assert AffectionLevel.STRANGER.threshold == 0
        assert AffectionLevel.ACQUAINTANCE.threshold == 100
        assert AffectionLevel.TRUST.threshold == 300
        assert AffectionLevel.INTIMATE.threshold == 600
        assert AffectionLevel.PARTNER.threshold == 1000

    def test_from_points_stranger(self):
        """0 分应为陌生"""
        assert AffectionLevel.from_points(0) == AffectionLevel.STRANGER
        assert AffectionLevel.from_points(50) == AffectionLevel.STRANGER
        assert AffectionLevel.from_points(99) == AffectionLevel.STRANGER

    def test_from_points_acquaintance(self):
        """100-299 分应为认识"""
        assert AffectionLevel.from_points(100) == AffectionLevel.ACQUAINTANCE
        assert AffectionLevel.from_points(200) == AffectionLevel.ACQUAINTANCE
        assert AffectionLevel.from_points(299) == AffectionLevel.ACQUAINTANCE

    def test_from_points_trust(self):
        """300-599 分应为信赖"""
        assert AffectionLevel.from_points(300) == AffectionLevel.TRUST
        assert AffectionLevel.from_points(450) == AffectionLevel.TRUST
        assert AffectionLevel.from_points(599) == AffectionLevel.TRUST

    def test_from_points_intimate(self):
        """600-999 分应为亲密"""
        assert AffectionLevel.from_points(600) == AffectionLevel.INTIMATE
        assert AffectionLevel.from_points(800) == AffectionLevel.INTIMATE
        assert AffectionLevel.from_points(999) == AffectionLevel.INTIMATE

    def test_from_points_partner(self):
        """1000+ 分应为伴侣"""
        assert AffectionLevel.from_points(1000) == AffectionLevel.PARTNER
        assert AffectionLevel.from_points(9999) == AffectionLevel.PARTNER

    def test_behavior_instructions_non_empty(self):
        """每个等级都有非空行为指令"""
        for level in AffectionLevel:
            instruction = level.behavior_instruction
            assert isinstance(instruction, str)
            assert len(instruction) > 10
            assert "关系状态" in instruction

    def test_address_non_empty(self):
        """每个等级都有称呼"""
        for level in AffectionLevel:
            assert isinstance(level.address, str)
            assert len(level.address) > 0


# ── AffectionState 数据类测试 ──


class TestAffectionState:
    """好感度状态数据类测试"""

    def test_new(self):
        """创建初始状态"""
        state = AffectionState.new(user_id=123)
        assert state.user_id == 123
        assert state.level == AffectionLevel.STRANGER
        assert state.points == 0

    def test_new_custom(self):
        """创建自定义初始状态"""
        state = AffectionState.new(user_id=456, initial_level=3, initial_points=350)
        assert state.level == AffectionLevel.TRUST
        assert state.points == 350

    def test_with_points_upgrade(self):
        """增加经验值触发升级"""
        state = AffectionState.new(user_id=1, initial_points=95)
        new_state = state.with_points(110)
        assert new_state.level == AffectionLevel.ACQUAINTANCE
        assert new_state.points == 110
        # 原状态不变（不可变数据类）
        assert state.level == AffectionLevel.STRANGER

    def test_with_points_no_upgrade(self):
        """增加经验值但未达阈值"""
        state = AffectionState.new(user_id=1, initial_points=50)
        new_state = state.with_points(80)
        assert new_state.level == AffectionLevel.STRANGER
        assert new_state.points == 80

    def test_with_points_skip_level(self):
        """一次加大量经验值跨越多个等级"""
        state = AffectionState.new(user_id=1, initial_points=50)
        new_state = state.with_points(1000)
        assert new_state.level == AffectionLevel.PARTNER
        assert new_state.points == 1000


# ── LLM 好感度评估测试 ──


class TestEvaluateAffectionDelta:
    """LLM 好感度评估函数测试"""

    @pytest.mark.asyncio
    async def test_positive_evaluation(self):
        """LLM 返回正数"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="5")
        state = AffectionState.new(user_id=1, initial_points=50)
        delta = await evaluate_affection_delta(mock_llm, state, "你好呀", "你好！")
        assert delta == 5

    @pytest.mark.asyncio
    async def test_negative_evaluation(self):
        """LLM 返回负数"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="-10")
        state = AffectionState.new(user_id=1, initial_points=50)
        delta = await evaluate_affection_delta(mock_llm, state, "滚", "...")
        assert delta == -10

    @pytest.mark.asyncio
    async def test_zero_evaluation(self):
        """LLM 返回 0"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="0")
        state = AffectionState.new(user_id=1, initial_points=50)
        delta = await evaluate_affection_delta(mock_llm, state, "哦", "嗯")
        assert delta == 0

    @pytest.mark.asyncio
    async def test_clamped_to_max(self):
        """超过 +20 被截断"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="50")
        state = AffectionState.new(user_id=1, initial_points=50)
        delta = await evaluate_affection_delta(mock_llm, state, "test", "test")
        assert delta == 20

    @pytest.mark.asyncio
    async def test_clamped_to_min(self):
        """低于 -20 被截断"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="-100")
        state = AffectionState.new(user_id=1, initial_points=50)
        delta = await evaluate_affection_delta(mock_llm, state, "test", "test")
        assert delta == -20

    @pytest.mark.asyncio
    async def test_unparseable_response_defaults_zero(self):
        """无法解析的回复默认 0"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="我无法判断")
        state = AffectionState.new(user_id=1, initial_points=50)
        delta = await evaluate_affection_delta(mock_llm, state, "test", "test")
        assert delta == 0

    @pytest.mark.asyncio
    async def test_llm_error_defaults_zero(self):
        """LLM 异常默认 0"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=Exception("API error"))
        state = AffectionState.new(user_id=1, initial_points=50)
        delta = await evaluate_affection_delta(mock_llm, state, "test", "test")
        assert delta == 0

    @pytest.mark.asyncio
    async def test_extracts_integer_from_text(self):
        """从文本中提取整数"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="我认为应该 +5 分")
        state = AffectionState.new(user_id=1, initial_points=50)
        delta = await evaluate_affection_delta(mock_llm, state, "test", "test")
        assert delta == 5

    @pytest.mark.asyncio
    async def test_prompt_includes_context(self):
        """评估 Prompt 包含上下文信息"""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="5")
        state = AffectionState.new(user_id=1, initial_points=50)
        await evaluate_affection_delta(mock_llm, state, "用户消息内容", "诺艾尔回复内容")
        # 验证调用参数中包含上下文
        call_args = mock_llm.complete.call_args
        messages = call_args[1].get("messages") or call_args[0][0]
        prompt_text = messages[0]["content"]
        assert "陌生" in prompt_text  # 当前关系阶段
        assert "50" in prompt_text  # 当前经验值
        assert "用户消息内容" in prompt_text
        assert "诺艾尔回复内容" in prompt_text


# ── 阶段变化过渡消息测试 ──


class TestTransitionMessage:
    """等级变化过渡消息测试"""

    def test_upgrade_to_acquaintance(self):
        """升级到认识有过渡消息"""
        msg = get_transition_message(AffectionLevel.STRANGER, AffectionLevel.ACQUAINTANCE)
        assert msg is not None
        assert "好感" in msg

    def test_upgrade_to_partner(self):
        """升级到伴侣有过渡消息"""
        msg = get_transition_message(AffectionLevel.INTIMATE, AffectionLevel.PARTNER)
        assert msg is not None
        assert "爱意" in msg

    def test_no_downgrade(self):
        """降级不触发过渡消息"""
        msg = get_transition_message(AffectionLevel.TRUST, AffectionLevel.ACQUAINTANCE)
        assert msg is None

    def test_same_level(self):
        """同级不触发过渡消息"""
        msg = get_transition_message(AffectionLevel.TRUST, AffectionLevel.TRUST)
        assert msg is None


# ── Prompt 层生成测试 ──


class TestPromptLayer:
    """好感度 Prompt 层生成测试"""

    def test_stranger_prompt(self):
        """陌生阶段的 Prompt"""
        state = AffectionState.new(user_id=1, initial_points=0)
        prompt = build_affection_prompt_layer(state)
        assert "陌生" in prompt
        assert "0/100" in prompt
        assert "刚刚认识" in prompt

    def test_trust_prompt(self):
        """信赖阶段的 Prompt"""
        state = AffectionState.new(user_id=1, initial_points=350)
        prompt = build_affection_prompt_layer(state)
        assert "信赖" in prompt
        assert "350/600" in prompt
        assert "信任" in prompt

    def test_partner_prompt(self):
        """伴侣阶段的 Prompt（∞ 显示）"""
        state = AffectionState.new(user_id=1, initial_points=1200)
        prompt = build_affection_prompt_layer(state)
        assert "伴侣" in prompt
        assert "1200/∞" in prompt
        assert "爱意" in prompt

    def test_prompt_contains_level_instruction(self):
        """Prompt 包含对应等级的行为指令"""
        for level in AffectionLevel:
            state = AffectionState(user_id=1, level=level, points=level.threshold)
            prompt = build_affection_prompt_layer(state)
            assert level.behavior_instruction in prompt


# ── AffectionSystem 集成测试 ──


class TestAffectionSystem:
    """好感度系统主类异步集成测试"""

    @pytest.fixture()
    def repo(self):
        return InMemoryAffectionRepository()

    @pytest.fixture()
    def mock_llm(self):
        """模拟 LLM 客户端"""
        mock = AsyncMock()
        # 默认返回 +5
        mock.complete = AsyncMock(return_value="5")
        return mock

    @pytest.fixture()
    def system(self, repo, mock_llm):
        return AffectionSystem(repo, mock_llm, initial_level=1, initial_points=0)

    @pytest.mark.asyncio
    async def test_get_state_creates_initial(self, system):
        """首次获取创建初始状态"""
        state = await system.get_state(user_id=999)
        assert state.user_id == 999
        assert state.level == AffectionLevel.STRANGER
        assert state.points == 0

    @pytest.mark.asyncio
    async def test_process_message_with_llm_positive(self, system, mock_llm):
        """LLM 返回正数，好感度增加"""
        mock_llm.complete = AsyncMock(return_value="10")
        result = await system.process_message(1, "你好呀", "你好！有什么可以帮你的吗？")
        assert result.points_delta == 10
        assert result.new_state.points == 10
        assert result.level_changed is False
        assert result.transition_message is None

    @pytest.mark.asyncio
    async def test_process_message_with_llm_negative(self, system, mock_llm):
        """LLM 返回负数，好感度减少"""
        mock_llm.complete = AsyncMock(return_value="-15")
        result = await system.process_message(1, "滚", "好的...")
        assert result.points_delta == -15

    @pytest.mark.asyncio
    async def test_process_message_neutral(self, system, mock_llm):
        """LLM 返回 0，好感度不变"""
        mock_llm.complete = AsyncMock(return_value="0")
        result = await system.process_message(1, "今天星期三", "这样啊")
        assert result.points_delta == 0
        assert result.new_state.points == 0

    @pytest.mark.asyncio
    async def test_points_never_negative(self, system, mock_llm):
        """经验值不会低于 0"""
        mock_llm.complete = AsyncMock(return_value="-20")
        # 先积累一些好感
        mock_llm.complete = AsyncMock(return_value="10")
        await system.process_message(1, "你好", "你好")
        # 再大幅减少
        mock_llm.complete = AsyncMock(return_value="-20")
        result = await system.process_message(1, "烦死了", "...")
        assert result.new_state.points >= 0

    @pytest.mark.asyncio
    async def test_level_upgrade(self, system, mock_llm):
        """好感度升级流程"""
        from src.systems.affection import AffectionState
        await system._repo.save(AffectionState(
            user_id=1, level=AffectionLevel.STRANGER, points=95
        ))
        mock_llm.complete = AsyncMock(return_value="15")
        result = await system.process_message(1, "我喜欢你", "谢、谢谢...")
        assert result.level_changed is True
        assert result.new_state.level == AffectionLevel.ACQUAINTANCE
        assert result.transition_message is not None

    @pytest.mark.asyncio
    async def test_level_upgrade_to_partner(self, system, mock_llm):
        """升级到伴侣等级"""
        from src.systems.affection import AffectionState
        await system._repo.save(AffectionState(
            user_id=1, level=AffectionLevel.INTIMATE, points=990
        ))
        mock_llm.complete = AsyncMock(return_value="15")
        result = await system.process_message(1, "我爱你，永远在一起", "我也爱你...")
        assert result.new_state.level == AffectionLevel.PARTNER
        assert result.transition_message is not None
        assert "爱意" in result.transition_message

    @pytest.mark.asyncio
    async def test_multiple_users_isolated(self, system, mock_llm):
        """多用户数据隔离"""
        mock_llm.complete = AsyncMock(return_value="15")
        result1 = await system.process_message(1, "喜欢你", "谢谢")
        result2 = await system.process_message(2, "谢谢你", "不客气")
        # 用户 1 加了 15，用户 2 也加了 15（从 0 开始）
        assert result1.new_state.points == 15
        assert result2.new_state.points == 15

    @pytest.mark.asyncio
    async def test_state_persistence(self, system, mock_llm):
        """状态持久化到仓库"""
        mock_llm.complete = AsyncMock(return_value="10")
        await system.process_message(1, "你好", "你好")
        state = await system._repo.get(1)
        assert state is not None
        assert state.points == 10

    @pytest.mark.asyncio
    async def test_get_prompt_layer_via_system(self, system, mock_llm):
        """通过系统获取 Prompt 层"""
        mock_llm.complete = AsyncMock(return_value="5")
        await system.process_message(1, "你好", "你好")
        state = await system.get_state(1)
        prompt = system.get_prompt_layer(state)
        assert "好感度状态" in prompt
        assert "陌生" in prompt  # 5 分仍在陌生阶段

    @pytest.mark.asyncio
    async def test_no_llm_defaults_zero(self, repo):
        """没有 LLM 时默认变化为 0"""
        system = AffectionSystem(repo, None, initial_level=1, initial_points=0)
        result = await system.process_message(1, "你好", "你好")
        assert result.points_delta == 0
        assert result.new_state.points == 0

    @pytest.mark.asyncio
    async def test_llm_called_with_context(self, system, mock_llm):
        """LLM 被传入正确的上下文"""
        mock_llm.complete = AsyncMock(return_value="5")
        await system.process_message(1, "用户说的消息", "诺艾尔的回复")
        call_args = mock_llm.complete.call_args
        messages = call_args[1].get("messages") or call_args[0][0]
        prompt_text = messages[0]["content"]
        assert "用户说的消息" in prompt_text
        assert "诺艾尔的回复" in prompt_text


# ── 边界条件测试 ──


class TestEdgeCases:
    """边界条件测试"""

    def test_all_levels_have_unique_behaviors(self):
        """每个等级的行为指令各不相同"""
        behaviors = [lvl.behavior_instruction for lvl in AffectionLevel]
        assert len(set(behaviors)) == len(behaviors)

    def test_enum_ordering(self):
        """枚举可比较大小"""
        assert AffectionLevel.STRANGER < AffectionLevel.ACQUAINTANCE
        assert AffectionLevel.PARTNER > AffectionLevel.TRUST

    def test_next_threshold(self):
        """next_threshold 属性"""
        assert AffectionLevel.STRANGER.next_threshold == 100
        assert AffectionLevel.ACQUAINTANCE.next_threshold == 300
        assert AffectionLevel.TRUST.next_threshold == 600
        assert AffectionLevel.INTIMATE.next_threshold == 1000
        assert AffectionLevel.PARTNER.next_threshold is None

    @pytest.mark.asyncio
    async def test_consecutive_messages_accumulate(self):
        """连续消息累积经验值"""
        repo = InMemoryAffectionRepository()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="10")
        system = AffectionSystem(repo, mock_llm, initial_level=1, initial_points=0)
        results = []
        for _ in range(5):
            r = await system.process_message(1, "你好", "你好")
            results.append(r)
        # 5 * 10 = 50 分
        assert results[-1].new_state.points == 50

    @pytest.mark.asyncio
    async def test_spam_same_message_no_llm(self):
        """没有 LLM 时重复消息不涨分"""
        repo = InMemoryAffectionRepository()
        system = AffectionSystem(repo, None, initial_level=1, initial_points=0)
        for _ in range(100):
            await system.process_message(1, "喜欢你", "谢谢")
        state = await system.get_state(1)
        assert state.points == 0  # 没有 LLM 评估，不变


# ── 经验值边界精确测试 ──


class TestPointsBoundaries:
    """经验值边界精确测试"""

    @pytest.mark.parametrize("points,expected_level", [
        (0, AffectionLevel.STRANGER),
        (1, AffectionLevel.STRANGER),
        (99, AffectionLevel.STRANGER),
        (100, AffectionLevel.ACQUAINTANCE),
        (101, AffectionLevel.ACQUAINTANCE),
        (299, AffectionLevel.ACQUAINTANCE),
        (300, AffectionLevel.TRUST),
        (599, AffectionLevel.TRUST),
        (600, AffectionLevel.INTIMATE),
        (999, AffectionLevel.INTIMATE),
        (1000, AffectionLevel.PARTNER),
        (10000, AffectionLevel.PARTNER),
    ])
    def test_boundary_values(self, points, expected_level):
        """边界值精确匹配"""
        assert AffectionLevel.from_points(points) == expected_level

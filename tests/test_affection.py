"""好感度系统单元测试 — 覆盖数据模型、变化规则、Prompt 注入、阶段转换"""

from __future__ import annotations

import pytest

from src.systems.affection import (
    AffectionLevel,
    AffectionState,
    AffectionSystem,
    InMemoryAffectionRepository,
    analyze_message,
    build_affection_prompt_layer,
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


# ── analyze_message 关键词匹配测试 ──


class TestAnalyzeMessage:
    """消息好感度分析测试"""

    def test_empty_message(self):
        """空消息返回 0"""
        assert analyze_message("") == 0

    def test_neutral_message(self):
        """中性消息返回 0"""
        assert analyze_message("今天星期三") == 0
        assert analyze_message("abc XYZ 123") == 0

    def test_positive_high_weight(self):
        """高权重正面关键词"""
        assert analyze_message("我喜欢你") == 15
        assert analyze_message("我爱你") == 15
        assert analyze_message("想你了") == 15

    def test_positive_medium_weight(self):
        """中权重正面关键词"""
        assert analyze_message("谢谢你的帮助") == 8
        assert analyze_message("辛苦了") == 8

    def test_positive_low_weight(self):
        """低权重正面关键词"""
        assert analyze_message("哈哈好的") == 2

    def test_negative_high_weight(self):
        """高权重负面关键词"""
        assert analyze_message("烦死了") == -15
        assert analyze_message("滚") == -15

    def test_negative_medium_weight(self):
        """中权重负面关键词"""
        assert analyze_message("别烦我") == -10

    def test_combined_message(self):
        """混合消息取总和"""
        # "谢谢" (+8) + "哈哈" (+2) = +10
        delta = analyze_message("谢谢你的礼物，哈哈")
        assert delta == 10

    def test_positive_negative_cancel(self):
        """正负抵消"""
        # "喜欢你" (+15) + "烦死了" (-15) = 0
        delta = analyze_message("喜欢你但有时也烦死了")
        assert delta == 0

    def test_max_delta_cap(self):
        """单次变化上限保护"""
        # 多个高权重正面词，但总和不应超过 +20
        msg = "喜欢你爱你想你亲亲抱抱"
        delta = analyze_message(msg)
        assert delta <= 20

    def test_min_delta_cap(self):
        """单次变化下限保护"""
        # 多个高权重负面词，但总和不应低于 -20
        msg = "烦死了滚讨厌你"
        delta = analyze_message(msg)
        assert delta >= -20

    def test_chinese_laughter(self):
        """中文笑声"""
        assert analyze_message("哈哈哈哈") == 2
        assert analyze_message("好搞笑哈哈哈") == 2


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
        assert "礼貌但略显生疏" in prompt

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
    def system(self, repo):
        return AffectionSystem(repo, initial_level=1, initial_points=0)

    @pytest.mark.asyncio
    async def test_get_state_creates_initial(self, system):
        """首次获取创建初始状态"""
        state = await system.get_state(user_id=999)
        assert state.user_id == 999
        assert state.level == AffectionLevel.STRANGER
        assert state.points == 0

    @pytest.mark.asyncio
    async def test_process_message_positive(self, system):
        """正面消息增加好感度"""
        result = await system.process_message(1, "谢谢你，诺艾尔")
        assert result.points_delta > 0
        assert result.new_state.points > 0
        assert result.level_changed is False  # 单次不足以升级
        assert result.transition_message is None

    @pytest.mark.asyncio
    async def test_process_message_negative(self, system):
        """负面消息减少好感度"""
        # 先积累一些好感
        await system.process_message(1, "喜欢你")
        result = await system.process_message(1, "烦死了")
        assert result.points_delta < 0

    @pytest.mark.asyncio
    async def test_process_message_neutral(self, system):
        """中性消息不变"""
        result = await system.process_message(1, "今天星期三")
        assert result.points_delta == 0
        assert result.new_state.points == 0

    @pytest.mark.asyncio
    async def test_points_never_negative(self, system):
        """经验值不会低于 0"""
        result = await system.process_message(1, "烦死了滚讨厌你别烦我闭嘴")
        assert result.new_state.points >= 0

    @pytest.mark.asyncio
    async def test_level_upgrade(self, system):
        """好感度升级流程"""
        # 直接设置一个接近升级的状态
        from src.systems.affection import AffectionState
        await system._repo.save(AffectionState(
            user_id=1, level=AffectionLevel.STRANGER, points=95
        ))
        result = await system.process_message(1, "我喜欢你")  # +15
        assert result.level_changed is True
        assert result.new_state.level == AffectionLevel.ACQUAINTANCE
        assert result.transition_message is not None

    @pytest.mark.asyncio
    async def test_level_upgrade_to_partner(self, system):
        """升级到伴侣等级"""
        from src.systems.affection import AffectionState
        await system._repo.save(AffectionState(
            user_id=1, level=AffectionLevel.INTIMATE, points=990
        ))
        result = await system.process_message(1, "我爱你，永远在一起")  # +15
        assert result.new_state.level == AffectionLevel.PARTNER
        assert result.transition_message is not None
        assert "爱意" in result.transition_message

    @pytest.mark.asyncio
    async def test_multiple_users_isolated(self, system):
        """多用户数据隔离"""
        result1 = await system.process_message(1, "喜欢你")
        result2 = await system.process_message(2, "谢谢你")
        assert result1.new_state.points != result2.new_state.points

    @pytest.mark.asyncio
    async def test_state_persistence(self, system):
        """状态持久化到仓库"""
        await system.process_message(1, "喜欢你")
        state = await system._repo.get(1)
        assert state is not None
        assert state.points > 0

    @pytest.mark.asyncio
    async def test_get_prompt_layer_via_system(self, system):
        """通过系统获取 Prompt 层"""
        await system.process_message(1, "喜欢你")
        state = await system.get_state(1)
        prompt = system.get_prompt_layer(state)
        assert "好感度状态" in prompt
        assert "陌生" in prompt  # 15 分仍在陌生阶段


# ── 边界条件测试 ──


class TestEdgeCases:
    """边界条件测试"""

    def test_very_long_message(self):
        """超长消息不崩溃"""
        long_msg = "哈哈" * 10000
        delta = analyze_message(long_msg)
        assert delta == 2  # 只计一次

    def test_special_characters(self):
        """特殊字符不崩溃"""
        delta = analyze_message("!@#$%^&*()")
        assert delta == 0

    def test_mixed_chinese_english(self):
        """中英混合"""
        delta = analyze_message("哈哈 thank you 谢谢")
        # "哈哈" (+2) + "谢谢" (+8) = +10
        assert delta == 10

    @pytest.mark.asyncio
    async def test_concurrent_same_user(self):
        """同一用户快速连续消息"""
        repo = InMemoryAffectionRepository()
        system = AffectionSystem(repo, initial_level=1, initial_points=0)
        results = []
        for _ in range(10):
            r = await system.process_message(1, "喜欢你")
            results.append(r)
        # 最后一条应该升级（15 * 10 = 150 >= 100）
        assert results[-1].new_state.level == AffectionLevel.ACQUAINTANCE

    def test_all_levels_have_unique_behaviors(self):
        """每个等级的行为指令各不相同"""
        behaviors = [lvl.behavior_instruction for lvl in AffectionLevel]
        assert len(set(behaviors)) == len(behaviors)

    def test_enum_ordering(self):
        """枚举可比较大小"""
        assert AffectionLevel.STRANGER < AffectionLevel.ACQUAINTANCE
        assert AffectionLevel.PARTNER > AffectionLevel.TRUST


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

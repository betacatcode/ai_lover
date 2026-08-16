"""记忆系统单元测试"""

from __future__ import annotations

import pytest
from datetime import datetime

from src.memory.embedding import EmbeddingService
from src.memory.profile import ProfileExtractor, ProfileRepository, ProfileFact
from src.memory.summary import SummaryGenerator, SummaryRepository, Summary
from src.memory.history import HistoryRepository
from src.memory.memory_system import MemorySystem, MemoryState


class TestEmbeddingService:
    """Embedding 服务测试"""

    def test_default_dimension(self):
        """默认维度是 512"""
        service = EmbeddingService()
        assert service.dimension == 512

    def test_not_loaded_initially(self):
        """初始状态未加载"""
        service = EmbeddingService()
        assert not service.is_loaded

    def test_encode_returns_zero_vector_when_not_loaded(self):
        """未加载时返回零向量"""
        service = EmbeddingService()
        result = service.encode("测试文本")
        assert len(result) == 512
        assert all(v == 0.0 for v in result)


class TestProfileFact:
    """画像事实测试"""

    def test_create_fact(self):
        """创建事实"""
        fact = ProfileFact(key="name", value="小明")
        assert fact.key == "name"
        assert fact.value == "小明"
        assert fact.updated_at  # 自动填充


class TestProfileExtractor:
    """画像提取器测试"""

    def test_parse_valid_json(self):
        """解析有效 JSON 响应"""
        extractor = ProfileExtractor()
        response = '[{"key": "name", "value": "小明"}, {"key": "pet", "value": "猫"}]'
        facts = extractor._parse_response(response)
        assert len(facts) == 2
        assert facts[0].key == "name"
        assert facts[0].value == "小明"

    def test_parse_invalid_json(self):
        """解析无效 JSON 返回空列表"""
        extractor = ProfileExtractor()
        facts = extractor._parse_response("not json")
        assert facts == []

    def test_parse_empty_array(self):
        """解析空数组"""
        extractor = ProfileExtractor()
        facts = extractor._parse_response("[]")
        assert facts == []

    def test_parse_mixed_content(self):
        """解析包含额外文本的响应"""
        extractor = ProfileExtractor()
        response = '这是结果：[{"key": "job", "value": "程序员"}] 结束'
        facts = extractor._parse_response(response)
        assert len(facts) == 1
        assert facts[0].key == "job"


class TestProfileRepository:
    """画像存储测试"""

    @pytest.mark.asyncio
    async def test_memory_save_and_get(self):
        """内存模式：保存后能读取"""
        repo = ProfileRepository()  # 无 DB URL，使用内存
        facts = [ProfileFact(key="name", value="小明")]
        await repo.upsert(user_id=1, new_facts=facts)

        result = await repo.get(1)
        assert len(result) == 1
        assert result[0]["key"] == "name"

    @pytest.mark.asyncio
    async def test_memory_upsert_updates_existing(self):
        """内存模式：合并更新已有事实"""
        repo = ProfileRepository()
        await repo.upsert(user_id=1, new_facts=[ProfileFact(key="name", value="小明")])
        await repo.upsert(user_id=1, new_facts=[ProfileFact(key="name", value="小红")])

        result = await repo.get(1)
        assert len(result) == 1
        assert result[0]["value"] == "小红"

    @pytest.mark.asyncio
    async def test_memory_max_facts_limit(self):
        """内存模式：超过上限时淘汰旧事实"""
        repo = ProfileRepository()
        facts = [ProfileFact(key=f"fact_{i}", value=f"value_{i}") for i in range(15)]
        await repo.upsert(user_id=1, new_facts=facts, max_facts=10)

        result = await repo.get(1)
        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_get_formatted_empty(self):
        """无画像时返回空字符串"""
        repo = ProfileRepository()
        result = await repo.get_formatted(999)
        assert result == ""


class TestSummary:
    """摘要测试"""

    def test_create_summary(self):
        """创建摘要"""
        summary = Summary(content="测试摘要", start_round=1, end_round=10)
        assert summary.content == "测试摘要"
        assert summary.start_round == 1
        assert summary.end_round == 10


class TestSummaryGenerator:
    """摘要生成器测试"""

    def test_parse_valid_json(self):
        """解析有效 JSON"""
        generator = SummaryGenerator()
        response = '{"content": "用户聊了喜欢猫的话题"}'
        content = generator._parse_response(response)
        assert content == "用户聊了喜欢猫的话题"

    def test_parse_invalid_json(self):
        """解析无效 JSON 返回 None"""
        generator = SummaryGenerator()
        content = generator._parse_response("not json")
        assert content is None


class TestSummaryRepository:
    """摘要存储测试"""

    @pytest.mark.asyncio
    async def test_memory_save_and_get(self):
        """内存模式：保存后能读取"""
        repo = SummaryRepository()
        summary = Summary(content="测试摘要", start_round=1, end_round=10)
        await repo.save(user_id=1, summary=summary)

        result = await repo.get_recent(1)
        assert len(result) == 1
        assert result[0]["content"] == "测试摘要"

    @pytest.mark.asyncio
    async def test_memory_get_recent_limit(self):
        """内存模式：限制返回数量"""
        repo = SummaryRepository()
        for i in range(5):
            await repo.save(user_id=1, summary=Summary(content=f"摘要{i}", start_round=i*10+1, end_round=(i+1)*10))

        result = await repo.get_recent(1, limit=2)
        assert len(result) == 2


class TestHistoryRepository:
    """历史存储测试"""

    @pytest.mark.asyncio
    async def test_memory_save_and_get(self):
        """内存模式：保存后能读取"""
        repo = HistoryRepository(window_size=10)
        await repo.save_round(
            user_id=1,
            user_message="你好",
            ai_reply="你好呀",
            raw_reply="你好呀！我是诺艾尔",
            emotion="开心",
            affection_level=1,
            affection_points=5,
        )

        result = await repo.get_recent(1)
        assert len(result) == 2  # user + assistant
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "你好"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "你好呀"

    @pytest.mark.asyncio
    async def test_memory_get_recent_text(self):
        """获取格式化文本"""
        repo = HistoryRepository(window_size=10)
        await repo.save_round(user_id=1, user_message="你好", ai_reply="你好呀", raw_reply="你好呀")

        text = await repo.get_recent_text(1)
        assert "用户：你好" in text
        assert "诺艾尔：你好呀" in text

    @pytest.mark.asyncio
    async def test_memory_window_trim(self):
        """内存模式：超出窗口裁剪"""
        repo = HistoryRepository(window_size=2)  # 只保留 2 轮
        for i in range(5):
            await repo.save_round(user_id=1, user_message=f"消息{i}", ai_reply=f"回复{i}", raw_reply=f"回复{i}")

        result = await repo.get_recent(1)
        # 应只保留最后 2 轮 = 4 条消息
        assert len(result) == 4


class TestMemoryState:
    """记忆状态测试"""

    def test_empty_state_no_memory(self):
        """空状态"""
        state = MemoryState()
        assert not state.has_memory

    def test_state_with_profile(self):
        """有画像"""
        state = MemoryState(profile_text="- name：小明")
        assert state.has_memory
        assert "小明" in state.get_profile_layer()

    def test_state_with_summaries(self):
        """有摘要"""
        state = MemoryState(recent_summaries=["上次聊了猫"])
        assert state.has_memory
        assert "上次聊了猫" in state.get_memory_layer()


class TestMemorySystem:
    """记忆系统主类测试"""

    @pytest.mark.asyncio
    async def test_get_state_empty(self):
        """无记忆时返回空状态"""
        memory = MemorySystem(trigger_rounds=10)
        state = await memory.get_state(user_id=1)
        assert not state.has_memory

    @pytest.mark.asyncio
    async def test_round_counter(self):
        """轮次计数"""
        memory = MemorySystem(trigger_rounds=10)
        memory._round_counters[1] = 5
        # 验证计数器递增通过 after_round
        # 这里只测试计数器逻辑

    def test_reset_counter(self):
        """重置计数器"""
        memory = MemorySystem(trigger_rounds=10)
        memory._round_counters[1] = 15
        memory.reset_counter(1)
        assert 1 not in memory._round_counters

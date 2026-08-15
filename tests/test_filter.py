"""测试回复后处理过滤层"""

import pytest

from src.chat.filter import filter_reply, get_max_length


class TestStripQuotes:
    """测试去除引号"""

    def test_chinese_quotes(self):
        text = "「你好」我是诺艾尔"
        result = filter_reply(text, affection_level=3)
        assert "「" not in result
        assert "」" not in result
        assert "你好" in result
        assert "我是诺艾尔" in result

    def test_english_quotes(self):
        text = '"Hello" she said'
        result = filter_reply(text, affection_level=3)
        assert '"' not in result
        assert "Hello" in result

    def test_mixed_quotes(self):
        text = "「你好」\"Hello\"『Hi』"
        result = filter_reply(text, affection_level=3)
        assert "「" not in result
        assert "」" not in result
        assert '"' not in result
        assert "『" not in result
        assert "』" not in result


class TestStripParenthetical:
    """测试去除括号动作描写"""

    def test_chinese_parens(self):
        text = "（诺艾尔歪头）你好呀"
        result = filter_reply(text, affection_level=3)
        assert "（" not in result
        assert "）" not in result
        assert "诺艾尔歪头" not in result
        assert "你好呀" in result

    def test_english_parens(self):
        text = "(smiles) Hello there"
        result = filter_reply(text, affection_level=3)
        assert "(" not in result
        assert ")" not in result
        assert "smiles" not in result

    def test_multiple_parens(self):
        text = "（歪头）（微笑）你好"
        result = filter_reply(text, affection_level=3)
        assert "歪头" not in result
        assert "微笑" not in result
        assert "你好" in result


class TestTruncateByAffectionLevel:
    """测试根据好感度截断长度"""

    def test_stranger_short(self):
        """陌生人：超过 60 字应截断"""
        text = "你好呀，我是诺艾尔，西风骑士团的女仆。今天天气真不错呢，你有什么需要帮忙的吗？我可以帮你打扫或者做饭哦。"
        result = filter_reply(text, affection_level=1)
        assert len(result) <= 60

    def test_stranger_within_limit(self):
        """陌生人：60 字内不截断"""
        text = "你好，我是诺艾尔。"
        result = filter_reply(text, affection_level=1)
        assert result == text

    def test_acquaintance_limit(self):
        """认识：超过 120 字应截断"""
        text = "你好呀，今天过得怎么样？" + "嗯" * 200
        result = filter_reply(text, affection_level=2)
        assert len(result) <= 120

    def test_trust_limit(self):
        """信赖：超过 200 字应截断"""
        text = "嗯" * 300
        result = filter_reply(text, affection_level=3)
        assert len(result) <= 200

    def test_partner_no_limit(self):
        """伴侣：800 字以内不截断"""
        text = "嗯" * 500
        result = filter_reply(text, affection_level=5)
        assert len(result) == 500


class TestTruncateBoundary:
    """测试截断位置在句子边界"""

    def test_truncate_at_period(self):
        """在句号处截断"""
        text = "你好呀。我是诺艾尔。西风骑士团的女仆。今天天气不错。有什么需要帮忙的吗？"
        result = filter_reply(text, affection_level=1, emotion="平静")
        # 应该在第一个句号后截断
        assert result.endswith("。") or result.endswith("？")

    def test_truncate_at_comma_fallback(self):
        """没有句号时在逗号处截断"""
        text = "你好呀，我是诺艾尔，西风骑士团的女仆，今天天气不错，有什么需要帮忙的吗"
        result = filter_reply(text, affection_level=1)
        # 截断后不应该太长
        assert len(result) <= 60


class TestEmptyAndEdgeCases:
    """测试空值和边界情况"""

    def test_empty_string(self):
        assert filter_reply("", affection_level=1) == ""

    def test_whitespace_only(self):
        assert filter_reply("   ", affection_level=1) == ""

    def test_only_quotes(self):
        text = "「」"
        result = filter_reply(text, affection_level=3)
        assert result == ""

    def test_only_parens(self):
        text = "（微笑）"
        result = filter_reply(text, affection_level=3)
        assert result == ""


class TestCleanWhitespace:
    """测试清理多余空白"""

    def test_multiple_newlines(self):
        text = "你好\n\n\n\n诺艾尔"
        result = filter_reply(text, affection_level=3)
        assert "\n\n\n" not in result

    def test_multiple_spaces(self):
        text = "你好    诺艾尔"
        result = filter_reply(text, affection_level=3)
        assert "    " not in result


class TestGetMaxLength:
    """测试获取最大长度配置"""

    def test_stranger(self):
        assert get_max_length(1) == 60

    def test_acquaintance(self):
        assert get_max_length(2) == 120

    def test_trust(self):
        assert get_max_length(3) == 200

    def test_intimate(self):
        assert get_max_length(4) == 400

    def test_partner(self):
        assert get_max_length(5) == 800

    def test_unknown_level(self):
        """未知等级返回默认值"""
        assert get_max_length(99) == 200


class TestCombinedFiltering:
    """测试组合过滤效果"""

    def test_full_pipeline(self):
        """完整流程：去引号 + 去括号 + 截断"""
        raw = "（诺艾尔歪头微笑）「你好呀，我是诺艾尔，西风骑士团的女仆。今天天气真不错呢，你有什么需要帮忙的吗？我可以帮你打扫或者做饭哦。对了，你喜欢吃什么？我可以做给你吃哦。」"
        result = filter_reply(raw, affection_level=1)
        # 没有引号括号
        assert "「" not in result
        assert "」" not in result
        assert "（" not in result
        assert "）" not in result
        # 长度限制
        assert len(result) <= 60
        # 保留核心内容
        assert "你好" in result

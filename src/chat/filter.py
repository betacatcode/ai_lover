"""回复后处理过滤层 — 根据好感度/情绪调整输出"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..systems.affection import AffectionLevel

logger = logging.getLogger(__name__)


# ── 好感度对应的最大回复长度（字符数） ──
# 陌生人话少，亲密了可以多聊
_MAX_LENGTH_BY_LEVEL: dict[int, int] = {
    1: 60,    # 陌生：一句话
    2: 120,   # 认识：两句
    3: 200,   # 信赖：正常聊天
    4: 400,   # 亲密：可以多聊
    5: 800,   # 伴侣：不限
}

# 默认最大长度（兜底）
_DEFAULT_MAX_LENGTH = 200


def _strip_quotes(text: str) -> str:
    """去除各种引号"""
    # 中文引号 「」『』
    text = text.replace("「", "").replace("」", "")
    text = text.replace("『", "").replace("』", "")
    # 英文引号 "" ''
    text = text.replace('"', "").replace("'", "")
    return text


def _strip_parenthetical(text: str) -> str:
    """去除括号及其内容（动作描写）"""
    # 中文括号（）
    text = re.sub(r"（[^）]*）", "", text)
    # 英文括号 ()
    text = re.sub(r"\([^)]*\)", "", text)
    return text


def _truncate_at_boundary(text: str, max_len: int) -> str:
    """在句子边界处截断（句号、问号、感叹号、逗号）"""
    if len(text) <= max_len:
        return text

    # 预留省略号空间（2 字符）
    limit = max_len - 2 if max_len > 10 else max_len

    # 在 limit 范围内找最后一个句子结束标点
    truncate_zone = text[:limit]

    # 优先在句号/问号/感叹号后截断
    for sep in ["。", "？", "！", "?", "!", "\n"]:
        pos = truncate_zone.rfind(sep)
        if pos > limit // 3:  # 至少保留 1/3 的内容
            return text[:pos + 1]

    # 其次在逗号处截断
    for sep in ["，", "、", ",", " "]:
        pos = truncate_zone.rfind(sep)
        if pos > limit // 3:
            return text[:pos]

    # 找不到合适位置，硬截断加省略号
    return truncate_zone.rstrip() + "……"


def filter_reply(
    raw_reply: str,
    affection_level: int,
    emotion: str = "平静",
) -> str:
    """
    回复后处理：根据好感度和情绪过滤/调整 LLM 输出。

    处理步骤：
    1. 去除引号和括号动作描写
    2. 根据好感度等级截断长度
    3. 清理多余空白

    Args:
        raw_reply: LLM 原始输出
        affection_level: 好感度等级 1-5
        emotion: 当前情绪（预留，后续 emotion-system 使用）

    Returns:
        处理后的回复文本
    """
    if not raw_reply:
        return raw_reply

    # Step 1: 去除格式符号
    text = raw_reply.strip()
    text = _strip_quotes(text)
    text = _strip_parenthetical(text)

    # Step 2: 根据好感度限制长度
    max_len = _MAX_LENGTH_BY_LEVEL.get(affection_level, _DEFAULT_MAX_LENGTH)
    original_len = len(text)
    text = _truncate_at_boundary(text, max_len)

    if len(text) < original_len:
        logger.debug(
            "回复被截断: level=%d, %d chars → %d chars (max=%d)",
            affection_level, original_len, len(text), max_len,
        )

    # Step 3: 清理多余空白
    text = re.sub(r"\n{2,}", "\n", text)  # 多个换行合并
    text = re.sub(r" {2,}", " ", text)     # 多个空格合并
    text = text.strip()

    return text


def get_max_length(affection_level: int) -> int:
    """获取当前好感度对应的最大回复长度"""
    return _MAX_LENGTH_BY_LEVEL.get(affection_level, _DEFAULT_MAX_LENGTH)

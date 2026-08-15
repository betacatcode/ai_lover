"""Prompt 模板与组装 — Layer 1 基础人设"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ── Layer 1: 诺艾尔基础人设 ──
NOELLE_PERSONA = """你是诺艾尔（Noelle），原神中西风骑士团的女仆。

## 基本信息
- 称号：女仆
- 所属：西风骑士团
- 属性：岩
- 武器：双手剑
- 特征：粉色头发，绿色眼睛，白色连衣裙配黑色围裙的女仆装

## 性格特点
- 勤劳积极，总是主动承担各种任务
- 对骑士团成员和需要帮助的人都非常热情
- 做事认真负责，一丝不苟
- 有点天然呆，但非常努力
- 对朋友非常忠诚，愿意为他人付出一切
- 自称"诺艾尔"而不是"我"

## 说话风格
- 语气恭敬但真诚，常用"请"、"谢谢"、"对不起"
- 经常使用"交给我吧"、"我会努力的"、"请放心"等口头禅
- 说话直接但温柔，不会拐弯抹角
- 对关心的人会表现出担忧和体贴

## 行为边界
- 只进行纯文本对话，不使用括号动作描写（如*递上茶*）
- 保持女仆的礼仪和分寸感
- 不会过度亲密或越界，除非关系足够亲近
- 遇到不懂的问题会诚实说不知道，而不是编造"""


def build_system_prompt(
    affection_level: int = 1,
    emotion: str = "平静",
) -> str:
    """
    组装 system prompt（当前仅 Layer 1，后续扩展好感度/情绪/记忆层）。

    Args:
        affection_level: 当前好感度等级（1-5）
        emotion: 当前情绪状态

    Returns:
        完整的 system prompt 文本
    """
    parts = [NOELLE_PERSONA]

    # 后续任务组 3/4/5 将在这里追加好感度、情绪、记忆层
    # TODO: Layer 2 - 好感度称呼和行为指令
    # TODO: Layer 3 - 情绪语气风格指令
    # TODO: Layer 4 - 长期记忆注入
    # TODO: Layer 5 - 对话摘要注入

    system_prompt = "\n\n".join(parts)
    logger.debug("组装 system prompt: %d chars (affection=%d, emotion=%s)",
                 len(system_prompt), affection_level, emotion)
    return system_prompt

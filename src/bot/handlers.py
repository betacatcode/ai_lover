"""消息处理器 — 处理用户消息并返回诺艾尔的回复"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)

# 路由器 — 所有消息处理器注册在此
router = Router(name="message_router")

# ChatService 实例（在 Bot 启动时注入）
_chat_service: Any = None


def set_chat_service(service: Any) -> None:
    """注入 ChatService 实例（由 main.py 在启动时调用）"""
    global _chat_service
    _chat_service = service


async def _safe_reply(message: Message, text: str) -> None:
    """安全回复，记录发送内容并捕获异常"""
    try:
        await message.answer(text)
        logger.info(
            "回复已发送 → user_id=%d, 长度=%d, 前50字=%r",
            message.from_user.id if message.from_user else 0,
            len(text),
            text[:50],
        )
    except Exception as e:
        logger.error("回复发送失败: %s", e, exc_info=True)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """处理 /start 命令 — 诺艾尔自我介绍"""
    await _safe_reply(
        message,
        "你好呀～我是诺艾尔！\n"
        "西风骑士团的女仆，有什么需要帮忙的尽管吩咐就好！\n"
        "……虽然现在是在这里陪你聊天啦。\n\n"
        "有什么想说的，直接发给我就好哦～",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """处理 /help 命令"""
    await _safe_reply(
        message,
        "【诺艾尔 Bot 指令】\n"
        "/start — 开始对话\n"
        "/status — 查看当前状态（好感度、情绪）\n"
        "/reset — 重置对话历史\n"
        "/help — 显示此帮助\n\n"
        "直接发消息就能和诺艾尔聊天啦～",
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    """处理 /status 命令 — 查看诺艾尔当前状态"""
    user_id = message.from_user.id if message.from_user else 0

    affection_level = "未知"
    affection_points = 0
    emotion = "平静"

    if _chat_service:
        affection_state = await _chat_service._affection.get_state(user_id)
        emotion_state = await _chat_service._emotion.get_state(user_id)
        affection_level = affection_state.level.title
        affection_points = affection_state.points
        emotion = emotion_state.current_emotion.value

    status_text = (
        f"【诺艾尔的状态】\n"
        f"好感度：{affection_level}（{affection_points} pts）\n"
        f"情绪：{emotion}"
    )
    await _safe_reply(message, status_text)


@router.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    """处理 /reset 命令 — 重置对话历史"""
    user_id = message.from_user.id if message.from_user else 0
    if _chat_service:
        _chat_service.reset_history(user_id)
    await _safe_reply(
        message,
        "好的，对话历史已经重置啦！\n"
        "让我们重新开始吧～",
    )


@router.message()
async def handle_message(message: Message) -> None:
    """
    处理普通文本消息 — 核心对话入口。

    通过 ChatService 调用 LLM 生成回复。
    """
    user_text = message.text or ""
    user_id = message.from_user.id if message.from_user else 0
    logger.info("收到消息 ← user_id=%d, 长度=%d, 内容=%r", user_id, len(user_text), user_text[:100])

    if not _chat_service:
        await _safe_reply(message, "抱歉，诺艾尔还在准备中，请稍后再试～")
        return

    # 通过 ChatService 调用 LLM
    result = await _chat_service.chat(user_id, user_text)

    # 组装回复（debug 模式附带状态信息）
    reply = result.reply
    if _chat_service._config.debug.enabled:
        user_id = message.from_user.id if message.from_user else 0

        # 获取当前情绪 emoji
        emotion_state = await _chat_service._emotion.get_state(user_id)
        emotion_emoji = emotion_state.emoji

        # 获取好感度对应爱心颜色
        from ..systems.emotion import _AFFECTION_HEART
        affection_state = await _chat_service._affection.get_state(user_id)
        heart = _AFFECTION_HEART.get(affection_state.level.value, "❤️")

        debug_info = (
            f"\n\n---\n"
            f"{heart} {result.affection_level} ({result.affection_points}) "
            f"{'+' if result.affection_delta >= 0 else ''}{result.affection_delta} | "
            f"{emotion_emoji} {result.emotion}"
        )
        reply = reply + debug_info

    await _safe_reply(message, reply)

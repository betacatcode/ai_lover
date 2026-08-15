"""FastAPI 应用工厂"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from .. import __version__
from ..chat.service import ChatService
from .schemas import ChatRequest, ChatResponse, HealthResponse

logger = logging.getLogger(__name__)


def create_app(chat_service: ChatService) -> FastAPI:
    """
    创建 FastAPI 应用。

    Args:
        chat_service: 聊天服务实例

    Returns:
        FastAPI 应用实例
    """
    app = FastAPI(
        title="Noelle Bot API",
        description="诺艾尔 Telegram Bot 的 REST 测试接口",
        version=__version__,
    )

    @app.get("/api/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        """健康检查"""
        return HealthResponse(version=__version__)

    @app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
    async def chat(request: ChatRequest) -> ChatResponse:
        """
        发送消息给诺艾尔并获取回复。

        - **user_id**: 用户 ID（用于隔离对话历史）
        - **message**: 用户消息文本（必填，1-2000 字符）
        """
        try:
            reply = await chat_service.chat(request.user_id, request.message)
            return ChatResponse(user_id=request.user_id, reply=reply)
        except Exception as e:
            logger.error("聊天处理异常: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="内部服务错误，请稍后重试") from e

    logger.info("FastAPI 应用创建完成")
    return app

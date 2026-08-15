"""FastAPI 请求/响应模型"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求"""
    user_id: int = Field(default=0, description="用户 ID")
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")


class ChatResponse(BaseModel):
    """聊天响应"""
    user_id: int = Field(..., description="用户 ID")
    reply: str = Field(..., description="诺艾尔的回复")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    version: str = "0.1.0"

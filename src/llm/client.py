"""LLM 客户端 — 封装 OpenAI 兼容 API 调用"""

from __future__ import annotations

import asyncio
import logging
import re

from openai import AsyncOpenAI, APIError, APIConnectionError, APITimeoutError

from ..config import LLMConfig
from .exceptions import LLMError, LLMTimeoutError

logger = logging.getLogger(__name__)

# 用于从错误信息中移除可能的 API Key
_KEY_RE = re.compile(r"(sk-|ak-)[A-Za-z0-9_-]{10,}")


def _sanitize_error(msg: str) -> str:
    """从错误信息中移除敏感信息（API Key 等）"""
    return _KEY_RE.sub("[REDACTED]", msg)


class LLMClient:
    """
    异步 LLM 客户端，封装 OpenAI 兼容 API。

    用法：
        client = LLMClient(config)
        reply = await client.complete(messages, system_prompt="...")
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.request_timeout,
        )
        logger.info(
            "LLMClient 初始化: base_url=%s, model=%s, timeout=%ds",
            config.base_url,
            config.model,
            config.request_timeout,
        )

    async def complete(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> str:
        """
        调用 LLM 生成回复。

        Args:
            messages: OpenAI 格式消息列表 [{"role": "user"|"assistant", "content": "..."}]
            system_prompt: 可选，作为 role=system 的消息首先发送

        Returns:
            模型生成的文本回复

        Raises:
            LLMTimeoutError: 请求超时
            LLMError: 其他 API 调用错误
        """
        # 组装完整消息列表
        full_messages: list[dict] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        logger.debug("LLM 请求: messages=%d 条", len(full_messages))

        try:
            response = await self._client.chat.completions.create(
                model=self.config.model,
                messages=full_messages,
                max_tokens=self.config.max_tokens,
            )
            reply = response.choices[0].message.content or ""
            logger.info("LLM 回复: %d chars", len(reply))
            return reply

        except APITimeoutError as e:
            logger.warning("LLM 超时: %s", e)
            raise LLMTimeoutError(self.config.request_timeout) from e

        except APIConnectionError as e:
            logger.error("LLM 连接错误: %s", _sanitize_error(str(e)))
            raise LLMError("无法连接到 LLM 服务，请检查网络") from e

        except APIError as e:
            # 从异常中移除敏感信息
            safe_msg = _sanitize_error(str(e))
            logger.error("LLM API 错误: %s", safe_msg)
            raise LLMError(f"LLM 调用失败: {safe_msg}") from e

        except Exception as e:
            safe_msg = _sanitize_error(str(e))
            logger.error("LLM 未知错误: %s", safe_msg, exc_info=True)
            raise LLMError("LLM 调用出现未知错误") from e

    async def close(self) -> None:
        """关闭客户端连接"""
        await self._client.close()

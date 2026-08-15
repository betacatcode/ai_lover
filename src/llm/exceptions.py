"""LLM 层异常定义"""


class LLMError(Exception):
    """LLM 调用异常基类"""

    def __init__(self, message: str = "LLM 调用失败"):
        # 确保不泄露 API Key 等敏感信息
        super().__init__(message)


class LLMTimeoutError(LLMError):
    """LLM 调用超时"""

    def __init__(self, timeout: float | None = None):
        msg = f"LLM 请求超时（{timeout}秒）" if timeout else "LLM 请求超时"
        super().__init__(msg)

"""Embedding 服务 — 使用 sentence-transformers 生成向量"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    本地 embedding 服务。

    使用 sentence-transformers 模型生成文本向量。
    默认模型: bge-small-zh-v1.5（512维，中文优化）。

    用法:
        service = EmbeddingService(model_name="BAAI/bge-small-zh-v1.5")
        service.load()  # 启动时预加载
        vector = service.encode("用户喜欢猫")
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5", dimension: int = 512) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._model = None

    def load(self) -> None:
        """预加载模型到内存（启动时调用一次）"""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            logger.info("Embedding 模型加载完成: %s (%d维)", self._model_name, self._dimension)
        except ImportError:
            logger.warning(
                "sentence-transformers 未安装，embedding 功能不可用。"
                "请运行: pip install sentence-transformers"
            )
            self._model = None
        except Exception as e:
            logger.error("Embedding 模型加载失败: %s", e)
            self._model = None

    def encode(self, text: str) -> list[float]:
        """
        将文本编码为向量。

        Args:
            text: 输入文本

        Returns:
            向量列表（512维），模型未加载时返回零向量
        """
        if self._model is None:
            logger.warning("Embedding 模型未加载，返回零向量")
            return [0.0] * self._dimension

        try:
            # 添加 BGE 模型前缀（检索场景）
            if not text.startswith("为这个句子生成表示"):
                text = f"为这个句子生成表示以用于检索：{text}"
            embedding = self._model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.error("Embedding 编码失败: %s", e)
            return [0.0] * self._dimension

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载"""
        return self._model is not None

    @property
    def dimension(self) -> int:
        """向量维度"""
        return self._dimension


@lru_cache(maxsize=1)
def get_embedding_service(
    model_name: str = "BAAI/bge-small-zh-v1.5",
    dimension: int = 512,
) -> EmbeddingService:
    """
    获取全局 EmbeddingService 单例。

    首次调用时创建并加载模型，后续调用返回缓存实例。
    """
    service = EmbeddingService(model_name=model_name, dimension=dimension)
    service.load()
    return service

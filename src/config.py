"""配置加载模块 — 从 config.yaml 读取所有配置"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


# 项目根目录（src/ 的上级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


@dataclass
class TelegramConfig:
    bot_token: str = ""
    allowed_user_id: int = 0
    proxy: str | None = None


@dataclass
class LLMConfig:
    base_url: str = "https://api.longcat.chat/openai/v1"
    api_key: str = ""
    model: str = "LongCat-2.0"
    request_timeout: int = 60
    max_tokens: int = 4096


@dataclass
class ChatConfig:
    history_window: int = 15
    summary_threshold: int = 30
    max_tokens: int = 4096
    request_timeout: int = 60


@dataclass
class AffectionConfig:
    initial_level: int = 1
    initial_points: int = 0


@dataclass
class EmotionConfig:
    default: str = "平静"


@dataclass
class DebugConfig:
    enabled: bool = True  # 开启时回复末尾附带好感度/情绪信息


@dataclass
class DBConfig:
    host: str = "127.0.0.1"
    port: int = 5432
    user: str = "postgres"
    password: str = ""
    database: str = "noelle"

    @property
    def url(self) -> str:
        """生成 PostgreSQL 连接 URL"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class EmbeddingConfig:
    mode: str = "local"
    model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    dimension: int = 384


@dataclass
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass
class MemoryConfig:
    db: DBConfig = field(default_factory=DBConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)


@dataclass
class AppConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    chat: ChatConfig = field(default_factory=ChatConfig)
    affection: AffectionConfig = field(default_factory=AffectionConfig)
    emotion: EmotionConfig = field(default_factory=EmotionConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    web: WebConfig = field(default_factory=WebConfig)


def load_config(path: str | Path | None = None) -> AppConfig:
    """从 YAML 文件加载配置，环境变量可覆盖"""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return _parse_config(raw)


def _parse_config(raw: dict) -> AppConfig:
    """解析原始 YAML 数据为类型化配置"""
    return AppConfig(
        telegram=TelegramConfig(
            bot_token=raw.get("telegram", {}).get("bot_token", ""),
            allowed_user_id=raw.get("telegram", {}).get("allowed_user_id", 0),
            proxy=raw.get("telegram", {}).get("proxy"),
        ),
        llm=LLMConfig(
            base_url=raw.get("llm", {}).get("base_url", "https://api.longcat.chat/openai/v1"),
            api_key=raw.get("llm", {}).get("api_key", ""),
            model=raw.get("llm", {}).get("model", "LongCat-2.0"),
            request_timeout=raw.get("chat", {}).get("request_timeout", 60),
            max_tokens=raw.get("chat", {}).get("max_tokens", 4096),
        ),
        chat=ChatConfig(
            history_window=raw.get("chat", {}).get("history_window", 15),
            summary_threshold=raw.get("chat", {}).get("summary_threshold", 30),
            max_tokens=raw.get("chat", {}).get("max_tokens", 4096),
            request_timeout=raw.get("chat", {}).get("request_timeout", 60),
        ),
        affection=AffectionConfig(
            initial_level=raw.get("affection", {}).get("initial_level", 1),
            initial_points=raw.get("affection", {}).get("initial_points", 0),
        ),
        emotion=EmotionConfig(
            default=raw.get("emotion", {}).get("default", "平静"),
        ),
        debug=DebugConfig(
            enabled=raw.get("debug", {}).get("enabled", True),
        ),
        memory=MemoryConfig(
            db=DBConfig(
                host=raw.get("memory", {}).get("db", {}).get("host", "127.0.0.1"),
                port=raw.get("memory", {}).get("db", {}).get("port", 5432),
                user=raw.get("memory", {}).get("db", {}).get("user", "postgres"),
                password=raw.get("memory", {}).get("db", {}).get("password", ""),
                database=raw.get("memory", {}).get("db", {}).get("database", "noelle"),
            ),
            embedding=EmbeddingConfig(
                mode=raw.get("memory", {}).get("embedding", {}).get("mode", "local"),
                model=raw.get("memory", {}).get("embedding", {}).get("model",
                         "paraphrase-multilingual-MiniLM-L12-v2"),
                dimension=raw.get("memory", {}).get("embedding", {}).get("dimension", 384),
            ),
        ),
        web=WebConfig(
            host=raw.get("web", {}).get("host", "127.0.0.1"),
            port=raw.get("web", {}).get("port", 8000),
        ),
    )


# 全局单例配置
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """获取全局配置单例（懒加载）"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: AppConfig) -> None:
    """手动设置全局配置（用于测试）"""
    global _config
    _config = config

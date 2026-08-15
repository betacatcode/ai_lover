"""系统层 — 好感度、情绪、记忆等角色系统"""

from .affection import (
    AffectionLevel,
    AffectionState,
    AffectionRepository,
    InMemoryAffectionRepository,
    PostgresAffectionRepository,
    AffectionSystem,
    build_affection_prompt_layer,
)

__all__ = [
    "AffectionLevel",
    "AffectionState",
    "AffectionRepository",
    "InMemoryAffectionRepository",
    "PostgresAffectionRepository",
    "AffectionSystem",
    "build_affection_prompt_layer",
]

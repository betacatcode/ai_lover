## Context

Prompt 组装器是整合所有系统的核心。当前 `src/chat/prompt.py` 仅包含 Layer 1（基础人设），需要扩展为完整的 Layer 1-5 组装器。

## Goals / Non-Goals

**Goals:**
- 按 Layer 1-5 顺序拼接 system prompt
- Token 估算和裁剪（超出上限时按优先级裁剪）
- 整合到对话处理管线

**Non-Goals:**
- 不修改各层内部逻辑（由各系统变更负责）

## Decisions

### Decision 1: 裁剪优先级

从低到高裁剪：对话历史 → 摘要 → 记忆 → 情绪 → 好感度 → 人设（人设不裁剪）。

**Why**: 人设是角色一致性的基础，对话历史冗余度最高。

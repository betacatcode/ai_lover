## Why

长期记忆让诺艾尔能记住用户画像、历史对话摘要，避免重复提问，使对话有连续感和成长感。使用 pgvector 实现向量语义检索。

## What Changes

- 实现 PostgreSQL 数据库初始化和表结构
- 实现用户画像提取和存储
- 实现对话历史持久化
- 实现对话摘要生成（超阈值时 LLM 压缩）
- 实现记忆 → Prompt 注入（Layer 4 + 5）

## Capabilities

### New Capabilities

- `memory`: 长期记忆系统，用户画像、对话摘要、向量检索、Prompt 注入

## Impact

- 代码: 新增 `src/memory/`
- 数据库: 新增 `user_profile`、`chat_history`、`summary` 表（含 pgvector 向量列）
- Prompt: 新增 Layer 4（记忆）和 Layer 5（摘要）

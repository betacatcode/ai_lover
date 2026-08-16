## Why

当前对话历史仅存储在内存滑动窗口中，服务重启后完全丢失。诺艾尔无法跨对话记住用户信息，每次聊天都像陌生人。需要持久化记忆系统让诺艾尔真正"认识"用户。

## What Changes

- 新增 `src/memory/` 模块，包含画像提取、摘要生成、向量检索
- 新增 3 张数据库表：`user_profile`、`chat_history`、`conversation_summary`
- 修改 `ChatHistoryManager`，从纯内存改为内存 + Postgres 双写
- 修改 `build_system_prompt()`，新增 Layer 4（画像）和 Layer 5（记忆）
- 修改 `ChatService`，对话写入 DB，每 10 轮异步触发画像提取和摘要生成
- 修改 `chat_history` 表结构，新增 `raw_content`、`emotion`、`affection_level`、`affection_points` 字段
- 新增 embedding 服务，使用 `bge-small-zh-v1-v1.5`（512 维，中文优化）
- 新增 APScheduler 异步任务调度（画像提取 + 摘要生成）
- 好感度/情绪配置新增 `memory_trigger_rounds = 10`

## Capabilities

### New Capabilities

- `memory`: 长期记忆系统，包含用户画像提取、对话摘要生成、向量语义检索、记忆 Prompt 注入

### Modified Capabilities

- 无（纯新增能力，不修改现有 spec）

## Impact

- 代码: 新增 `src/memory/` 模块（~8 个文件）
- 数据库: 新增 3 张表，修改现有 `ChatHistoryManager`
- Prompt: 新增 Layer 4-5，system prompt 增加约 500 tokens
- 依赖: 新增 `sentence-transformers`、`pgvector` 扩展
- LLM 调用: 每 10 轮新增 2 次异步调用（不阻塞用户回复）

## Purpose

长期记忆系统存储用户画像和对话历史摘要，使诺艾尔能够跨对话记住用户的偏好、习惯和重要事件，实现真正的"认识你"而非每次从零开始。

## ADDED Requirements

### Requirement: 对话历史持久化
系统 SHALL 将每轮对话（用户消息 + AI 回复）持久化存储到 PostgreSQL，包含状态快照和原始输出。

#### Scenario: 对话写入数据库
- **WHEN** 一轮对话结束
- **THEN** 系统 SHALL 将用户消息和 AI 回复写入 `chat_history` 表，包含 `emotion`、`affection_level`、`affection_points` 状态快照，以及 `raw_content`（AI 原始输出）

#### Scenario: 服务重启后恢复历史
- **WHEN** 系统重启后用户发起对话
- **THEN** 系统 SHALL 从 `chat_history` 表读取最近 10 轮对话作为滑动窗口上下文

#### Scenario: 滑动窗口保持 10 轮
- **WHEN** 内存中的对话历史超过 10 轮（20 条消息）
- **THEN** 系统 SHALL 裁剪早期消息，仅保留最近 10 轮在内存中

### Requirement: 用户画像提取
系统 SHALL 每 10 轮对话后，通过 LLM 从对话中提取用户结构化事实并存储。

#### Scenario: 提取用户偏好
- **WHEN** 异步任务读取最近 10 轮对话
- **THEN** 系统 SHALL 调用 LLM 提取用户事实（姓名、喜好、职业、近期事件等），返回结构化 JSON

#### Scenario: 画像合并更新
- **WHEN** LLM 返回新事实列表
- **THEN** 系统 SHALL 与现有事实合并：已存在的 key 更新 value 和 updated_at，新 key 插入

#### Scenario: 画像注入 Prompt
- **WHEN** 组装对话 Prompt 时
- **THEN** 系统 SHALL 从 `user_profile` 表读取所有事实，格式化为文本注入 Layer 4

#### Scenario: 画像上限控制
- **WHEN** 用户画像事实数量超过 10 条
- **THEN** 系统 SHALL 仅注入最近更新的 10 条事实，避免 Prompt 膨胀

### Requirement: 对话摘要生成
系统 SHALL 每 10 轮对话后，通过 LLM 生成一段摘要，覆盖该 10 轮的核心内容。

#### Scenario: 触发摘要生成
- **WHEN** 对话轮次达到 10 的倍数（第 10、20、30...轮）
- **THEN** 系统 SHALL 触发异步任务，读取该 10 轮原文，调用 LLM 生成摘要

#### Scenario: 摘要内容
- **WHEN** LLM 生成摘要
- **THEN** 摘要 SHALL 包含：讨论的主要话题、用户表达的重要信息、诺艾尔做出的承诺或约定、用户情绪变化

#### Scenario: 摘要独立存储
- **WHEN** 摘要生成后
- **THEN** 系统 SHALL 将摘要作为独立记录写入 `conversation_summary` 表，包含 `start_round` 和 `end_round`

#### Scenario: 摘要注入 Prompt
- **WHEN** 组装对话 Prompt 时
- **THEN** 系统 SHALL 注入最近 2 段摘要到 Layer 5

### Requirement: 向量语义检索
系统 SHALL 使用 pgvector 对摘要和画像进行语义检索，召回与当前对话相关的记忆。

#### Scenario: 语义检索召回
- **WHEN** 用户发起新消息
- **THEN** 系统 SHALL 将用户消息编码为向量，从 `conversation_summary` 和 `user_profile` 中检索最相关的 Top-3 记忆片段

#### Scenario: embedding 生成
- **WHEN** 需要生成向量时
- **THEN** 系统 SHALL 使用 `bge-small-zh-v1.5` 模型（512 维）生成 embedding

#### Scenario: 检索结果注入
- **WHEN** 语义检索返回结果
- **THEN** 系统 SHALL 将结果注入 Layer 5 的"相关记忆"部分

### Requirement: 异步任务执行
画像提取和摘要生成 SHALL 在异步任务中执行，不阻塞用户回复。

#### Scenario: 异步触发
- **WHEN** 对话轮次达到触发条件
- **THEN** 系统 SHALL 在后台调度异步任务，用户立即收到回复

#### Scenario: 任务失败不影响对话
- **WHEN** 异步任务执行失败（LLM 超时、DB 错误等）
- **THEN** 系统 SHALL 记录错误日志，不重试，下次触发时补执行

### Requirement: 记忆隐私
所有记忆数据 SHALL 仅关联到单一用户，不与其他用户或外部服务共享。

#### Scenario: 数据隔离
- **WHEN** 系统运行时
- **THEN** 所有记忆数据 SHALL 仅关联到配置的 Telegram 用户 ID

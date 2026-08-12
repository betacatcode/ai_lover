## Purpose

长期记忆系统存储用户画像和对话历史摘要，使诺艾尔能够跨对话记住用户的偏好、习惯和重要事件，实现真正的"认识你"而非每次从零开始。

## ADDED Requirements

### Requirement: 用户画像存储
系统 SHALL 从对话中提取并持久化存储用户的结构化事实（偏好、习惯、基本信息）。

#### Scenario: 提取用户偏好
- **WHEN** 用户提到"我喜欢猫"或"我讨厌下雨天"
- **THEN** 系统 SHALL 提取该事实并存储到用户画像中

#### Scenario: 画像注入 Prompt
- **WHEN** 组装对话 Prompt 时
- **THEN** 系统 SHALL 将相关用户画像事实注入到 system prompt 中

#### Scenario: 画像更新
- **WHEN** 用户说"其实我现在更喜欢狗了"
- **THEN** 系统 SHALL 更新对应的画像事实

### Requirement: 对话摘要压缩
当对话历史超出上下文窗口时，系统 SHALL 对早期对话生成摘要，保留关键信息。

#### Scenario: 触发摘要压缩
- **WHEN** 对话轮数超过设定的窗口阈值（如 30 轮）
- **THEN** 系统 SHALL 调用 LLM 对超出窗口的早期对话生成摘要

#### Scenario: 摘要内容
- **WHEN** 生成对话摘要时
- **THEN** 摘要 SHALL 包含：讨论的主要话题、用户表达的重要信息、诺艾尔做出的承诺或约定、用户情绪变化

#### Scenario: 摘要持久化
- **WHEN** 摘要生成后
- **THEN** 系统 SHALL 持久化存储摘要，后续对话可引用

### Requirement: 记忆检索
系统 SHALL 基于向量语义检索，在对话时自动召回与当前话题相关的记忆片段。

#### Scenario: 语义检索召回
- **WHEN** 用户提到"上次我们聊的那个游戏"
- **THEN** 系统 SHALL 将当前输入编码为向量，从 pgvector 中检索最相关的记忆片段（对话摘要、用户画像事实）并注入上下文

#### Scenario: 检索结果控制
- **WHEN** 执行记忆检索时
- **THEN** 系统 SHALL 返回 Top-K（默认 5 条）最相关的记忆片段，避免 prompt 膨胀

### Requirement: 记忆持久化
所有记忆数据（用户画像、对话摘要、对话历史） SHALL 持久化存储到 PostgreSQL，向量数据使用 pgvector 扩展。

#### Scenario: 服务重启后恢复记忆
- **WHEN** 系统重启
- **THEN** 所有记忆数据 SHALL 完整恢复

### Requirement: 记忆隐私
系统 SHALL 仅存储单一用户的数据，不与其他用户或外部服务共享。

#### Scenario: 数据隔离
- **WHEN** 系统运行时
- **THEN** 所有记忆数据 SHALL 仅关联到配置的 Telegram 用户 ID

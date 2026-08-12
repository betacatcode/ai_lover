## Purpose

多轮文本对话是用户与诺艾尔交互的核心入口。系统 SHALL 基于诺艾尔的动态状态（好感度、情绪、记忆）实时组装 Prompt，通过 Telegram Bot 提供自然、连贯的对话体验。

## ADDED Requirements

### Requirement: Telegram 消息收发
系统 SHALL 通过 Telegram Bot API 接收用户发送的文本消息，并将诺艾尔的回复发送回同一对话。

#### Scenario: 接收并回复文本消息
- **WHEN** 用户通过 Telegram 发送一条文本消息
- **THEN** 系统处理该消息并通过 Telegram 返回诺艾尔的回复

#### Scenario: 回复超时或失败
- **WHEN** LLM 调用超时或失败
- **THEN** 系统向用户返回一条友好的错误提示，不暴露技术细节

### Requirement: 诺艾尔人设一致性
系统 SHALL 确保诺艾尔在所有对话中保持原神角色的一致性，包括性格、语言风格和行为模式。

#### Scenario: 语言风格一致
- **WHEN** 用户发送任意消息
- **THEN** 诺艾尔的回复 SHALL 使用诺艾尔的口吻（自称"诺艾尔"、语气恭敬但真诚、勤劳积极）

#### Scenario: 不使用动作描写
- **WHEN** 诺艾尔回复时
- **THEN** 回复 SHALL 为纯文本对话，不包含括号动作描写（如"*递上茶*"），以保持自然并为未来语音功能兼容

### Requirement: 多轮对话上下文
系统 SHALL 维护对话历史，使诺艾尔能够引用之前提到的内容，保持对话连贯性。

#### Scenario: 引用之前话题
- **WHEN** 用户提到之前对话中讨论过的事情
- **THEN** 诺艾尔 SHALL 能够基于对话历史做出连贯回应

#### Scenario: 对话历史过长
- **WHEN** 对话轮数超过上下文窗口限制
- **THEN** 系统 SHALL 对早期对话进行摘要压缩，保留关键信息，丢弃冗余细节

### Requirement: 动态 Prompt 组装
系统 SHALL 在每次生成回复前，实时组装包含以下层的完整 system prompt：基础人设、当前好感度状态、当前情绪状态、长期记忆摘要、近期对话历史。

#### Scenario: 好感度影响回复风格
- **WHEN** 好感度从 Lv.2 提升到 Lv.3
- **THEN** 诺艾尔的称呼和行为模式 SHALL 随之变化（如从"大人"改口为"你"）

#### Scenario: 情绪影响回复风格
- **WHEN** 诺艾尔当前情绪为"担心"
- **THEN** 回复 SHALL 体现担心的语气（如关心、询问状态）

### Requirement: 单用户识别
系统 SHALL 将 Telegram 用户 ID 识别为唯一用户，所有记忆和状态关联到此用户。

#### Scenario: 唯一用户对话
- **WHEN** 配置的 Telegram 用户发送消息
- **THEN** 系统 SHALL 加载该用户的记忆和状态进行对话

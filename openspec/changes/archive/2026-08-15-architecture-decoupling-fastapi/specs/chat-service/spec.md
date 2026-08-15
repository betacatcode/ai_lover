## Purpose

聊天业务层，负责管理对话历史、组装动态 Prompt、调用 LLM 生成回复。与具体传输方式（Telegram/HTTP）解耦，可被多个应用层复用。

## ADDED Requirements

### Requirement: 聊天服务提供统一对话接口
系统 SHALL 提供一个聊天服务，接收用户 ID 和消息文本，返回诺艾尔的回复文本。

#### Scenario: 处理用户消息
- **WHEN** 传入有效的 user_id 和 message
- **THEN** 系统加载对话历史、组装 Prompt、调用 LLM、保存历史并返回回复

#### Scenario: LLM 调用失败时的降级回复
- **WHEN** LLM 调用抛出异常（超时或 API 错误）
- **THEN** 返回一条友好的降级回复（如"抱歉，诺艾尔现在有点忙，请稍后再试"），不暴露技术细节

### Requirement: 对话历史滑动窗口管理
系统 SHALL 维护每个用户的对话历史，仅保留最近 N 轮（N 由配置指定）供 LLM 使用。

#### Scenario: 历史未超窗口
- **WHEN** 对话轮数未超过配置的 history_window
- **THEN** 所有历史消息均发送给 LLM

#### Scenario: 历史超出窗口
- **WHEN** 对话轮数超过配置的 history_window
- **THEN** 仅保留最近 N 轮消息，早期消息被丢弃（后续由摘要系统处理）

### Requirement: 动态 Prompt 组装
系统 SHALL 在每次回复前实时组装 system prompt，包含基础人设、当前好感度状态、当前情绪状态（后续还包括记忆和摘要）。

#### Scenario: 基础人设注入
- **WHEN** 组装 system prompt
- **THEN** 基础人设（Layer 1）始终作为 system prompt 的第一部分

#### Scenario: 好感度状态注入
- **WHEN** 好感度等级变化后
- **THEN** system prompt 中的称呼和行为指令 SHALL 对应新的等级

### Requirement: 单用户状态隔离
系统 SHALL 按 user_id 隔离对话历史、好感度和情绪状态。

#### Scenario: 不同用户独立对话
- **WHEN** 两个不同 user_id 的用户分别发送消息
- **THEN** 各自的历史和状态互不影响

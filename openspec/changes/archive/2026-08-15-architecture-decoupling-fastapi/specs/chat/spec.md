## MODIFIED Requirements

### Requirement: 诺艾尔人设一致性
系统 SHALL 确保诺艾尔在所有对话中保持原神角色的一致性，包括性格、语言风格和行为模式。

#### Scenario: 语言风格一致
- **WHEN** 用户通过任意渠道（Telegram 或 HTTP）发送消息
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
- **THEN** 系统 SHALL 仅使用最近 N 轮对话，早期对话后续由摘要压缩处理

### Requirement: 动态 Prompt 组装
系统 SHALL 在每次生成回复前，实时组装包含以下层的完整 system prompt：基础人设、当前好感度状态、当前情绪状态、长期记忆摘要、近期对话历史。

#### Scenario: 好感度影响回复风格
- **WHEN** 好感度从 Lv.2 提升到 Lv.3
- **THEN** 诺艾尔的称呼和行为模式 SHALL 随之变化（如从"大人"改口为"你"）

#### Scenario: 情绪影响回复风格
- **WHEN** 诺艾尔当前情绪为"担心"
- **THEN** 回复 SHALL 体现担心的语气（如关心、询问状态）

### Requirement: 聊天服务与传输解耦
聊天业务逻辑 SHALL 不依赖特定的传输渠道（Telegram/HTTP），通过统一的聊天服务接口被多个应用层调用。

#### Scenario: Telegram 和 HTTP 共用同一聊天服务
- **WHEN** 用户通过 Telegram 或 HTTP 发送相同消息
- **THEN** 聊天服务 SHALL 返回相同的回复结果（不考虑传输格式差异）

## Purpose

封装底层大模型调用，提供与业务无关的统一接口，使上层聊天服务和传输渠道可以不关心 LLM 的具体实现细节。

## ADDED Requirements

### Requirement: LLM 客户端提供统一调用接口
系统 SHALL 提供一个 LLM 客户端，接收消息列表（OpenAI 格式）并返回模型生成的文本回复。

#### Scenario: 成功调用 LLM
- **WHEN** 客户端收到有效的消息列表并调用 LLM
- **THEN** 返回模型生成的文本回复

#### Scenario: LLM 调用超时
- **WHEN** LLM 请求超过配置的超时时间
- **THEN** 抛出超时异常，由上层处理

#### Scenario: LLM 调用失败
- **WHEN** LLM API 返回错误（如网络错误、认证失败）
- **THEN** 抛出包含错误原因的异常，不暴露敏感信息（如 API Key）

### Requirement: LLM 客户端可配置
系统 SHALL 允许通过配置指定 LLM 的 base URL、API Key、模型名称和超时时间。

#### Scenario: 使用配置初始化客户端
- **WHEN** 使用配置文件中的 `llm` 段初始化客户端
- **THEN** 客户端使用对应的 base URL、API Key 和模型名称

### Requirement: LLM 客户端支持系统提示
系统 SHALL 在每次调用时将系统提示（system prompt）作为消息列表的第一条发送给 LLM。

#### Scenario: 注入系统提示
- **WHEN** 上层传入系统提示文本和用户消息
- **THEN** 系统提示作为 role=system 的消息首先发送，然后是对话历史

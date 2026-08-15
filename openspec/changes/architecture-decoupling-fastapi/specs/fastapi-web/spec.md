## Purpose

提供 FastAPI REST 接口，使聊天功能可通过 HTTP 调用进行测试，不依赖 Telegram。

## ADDED Requirements

### Requirement: 聊天 REST 端点
系统 SHALL 提供 `POST /api/chat` 端点，接收用户消息并返回诺艾尔的回复。

#### Scenario: 发送聊天消息
- **WHEN** 向 `/api/chat` 发送 POST 请求，body 包含 `{user_id, message}`
- **THEN** 返回 200，body 包含 `{reply, user_id}`

#### Scenario: 缺少必填字段
- **WHEN** 请求 body 缺少 `message` 字段
- **THEN** 返回 422 验证错误

### Requirement: 健康检查端点
系统 SHALL 提供 `GET /api/health` 端点用于健康检查。

#### Scenario: 健康检查
- **WHEN** 请求 `/api/health`
- **THEN** 返回 200，body 包含 `{"status": "ok"}`

### Requirement: 服务可配置
系统 SHALL 允许通过配置指定 FastAPI 的监听 host 和 port。

#### Scenario: 使用配置启动
- **WHEN** 使用配置文件中的 `web` 段启动服务
- **THEN** 服务监听配置的 host:port

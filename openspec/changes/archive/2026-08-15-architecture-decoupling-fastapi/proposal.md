## Why

当前代码将 Telegram 消息处理、聊天业务逻辑和 LLM 调用耦合在一起，导致：(1) 无法脱离 Telegram 独立测试（必须去 Telegram 发消息才能验证）；(2) 聊天逻辑无法被其他传输渠道复用；(3) LLM 调用层无法独立替换或 mock。需要先做架构解耦，再在应用层引入 FastAPI 提供 HTTP 测试接口。

## What Changes

- **BREAKING**: 重构 `src/` 目录结构，按三层分离关注点：
  - `src/llm/` — 底层大模型接口调用层（与具体业务无关）
  - `src/chat/` — 聊天业务层（对话管理、Prompt 组装、历史滑动窗口、好感度/情绪注入）
  - `src/web/` — 应用层新增 FastAPI REST 接口
  - `src/bot/` — 应用层 Telegram Bot（简化为纯传输适配）
- 新增 FastAPI 应用（`uvicorn` 运行），暴露 `/api/chat` 端点
- 新增 `src/chat/service.py` — 统一的聊天服务入口，被 Telegram 和 FastAPI 共同调用
- 新增 `src/llm/client.py` — LLM 客户端封装（OpenAI SDK → LongCat）
- 新增 `src/llm/prompt.py` — Prompt 模板与组装逻辑
- 配置文件扩展：`web` 段（host/port）

## Capabilities

### New Capabilities

- `llm-client`: 底层大模型调用层，封装 OpenAI 兼容 API，提供统一的 `complete(messages) -> str` 接口
- `chat-service`: 聊天业务层，管理对话历史（滑动窗口）、组装动态 Prompt、调用 LLM、处理错误
- `fastapi-web`: FastAPI REST 接口，暴露 `/api/chat` 用于 HTTP 测试

### Modified Capabilities

- `chat`（现有 `specs/chat/spec.md`）：原"Telegram 消息收发"需求拆分为"聊天服务接口"和"传输适配"，聊天服务不再依赖 Telegram

## Impact

- **代码**: `src/` 目录重构，现有 `bot/handlers.py` 改为调用 `chat-service`
- **依赖**: 新增 `fastapi`, `uvicorn`
- **API**: 新增 REST 端点 `POST /api/chat`（请求: `{user_id, message}`，响应: `{reply}`）
- **配置**: `config.yaml` 新增 `web` 段

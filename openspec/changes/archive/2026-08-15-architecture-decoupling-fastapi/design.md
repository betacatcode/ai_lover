## Context

当前 `src/bot/handlers.py` 直接处理 Telegram 消息并硬编码了 echo 回复，LLM 调用逻辑尚未实现。项目需要重构为三层架构，并引入 FastAPI 作为第二个应用层入口。详见 proposal.md。

**当前代码状态：**
- `src/bot/handlers.py` — Telegram 消息处理器（含占位 echo 回复）
- `src/bot/bot.py` — Bot/Dispatcher 工厂
- `src/config.py` — 配置加载（已完善）
- `src/llm/`, `src/chat/` — 空目录

## Goals / Non-Goals

**Goals:**
- 三层解耦：`llm`（底层）→ `chat`（业务层）→ `bot`/`web`（应用层）
- 聊天业务逻辑可被 Telegram 和 FastAPI 复用
- FastAPI 提供 `/api/chat` 端点用于独立测试
- 新增 FastAPI 依赖（`fastapi`, `uvicorn`）

**Non-Goals:**
- 不实现好感度/情绪/记忆的具体逻辑（后续任务组 3/4/5）
- 不修改现有 config.py 和 bot.py 的连接/代理逻辑
- 不做数据库 schema 变更

## Decisions

### Decision 1: 三层架构分层

```
┌─────────────────────────────────────────────────────┐
│  Application Layer（应用层）                          │
│  ┌──────────────┐     ┌────────────────────┐        │
│  │ src/bot/     │     │ src/web/           │        │
│  │ Telegram Bot │     │ FastAPI REST API   │        │
│  └──────┬───────┘     └────────┬───────────┘        │
│         │  都调用               │                    │
├─────────┴──────────────────────┴────────────────────┤
│  Chat Business Layer（聊天业务层）                     │
│  ┌────────────────────────────────────────┐         │
│  │ src/chat/                              │         │
│  │  service.py — 统一聊天入口              │         │
│  │  history.py — 滑动窗口历史管理           │         │
│  │  prompt.py — Prompt 模板组装            │         │
│  └──────────────┬─────────────────────────┘         │
│                 │ 调用                                │
├─────────────────┴───────────────────────────────────┤
│  LLM Interface Layer（大模型接口层）                   │
│  ┌────────────────────────────────────────┐         │
│  │ src/llm/                               │         │
│  │  client.py — OpenAI SDK 封装            │         │
│  └────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────┘
```

**Why**: 应用层只负责传输协议适配（Telegram Bot API / HTTP），聊天业务层处理核心逻辑，LLM 层只关心模型调用。任何一层可独立替换。

**Alternatives**: 两层架构（合并 chat + llm）—— 不够清晰，LLM mock 测试需要侵入业务逻辑。

### Decision 2: 聊天服务入口设计

`ChatService` 类作为统一入口，依赖注入 `LLMClient` 和配置：

```python
class ChatService:
    def __init__(self, llm_client: LLMClient, config: ChatConfig)
    async def chat(self, user_id: int, message: str) -> str
    def get_history(self, user_id: int) -> list
    def reset_history(self, user_id: int)
```

**Why**: 依赖注入使得测试时可用 mock LLM 替换真实调用。`async` 兼容 aiogram 和 FastAPI 的异步模型。

### Decision 3: FastAPI 集成方式

FastAPI 应用通过工厂函数创建，复用同一个 `ChatService` 实例：

```python
def create_app(chat_service: ChatService) -> FastAPI
```

配置新增 `web` 段：
```yaml
web:
  host: "127.0.0.1"
  port: 8000
```

**Why**: 工厂模式便于测试时注入 mock 服务。默认仅监听 localhost 避免暴露到公网。

### Decision 4: 对话历史存储（MVP 阶段）

MVP 阶段对话历史存内存（`dict[user_id, list]`），后续任务组 5 再持久化到 PostgreSQL。

**Why**: 先验证架构，持久化属于数据层优化，不影响三层架构设计。

## Risks / Trade-offs

### Risk: 内存历史重启丢失
- **Mitigation**: MVP 阶段可接受，后续任务组 5 加 PostgreSQL 持久化

### Risk: FastAPI 和 Telegram Bot 并发访问 ChatService
- **Mitigation**: ChatService 使用 asyncio 原生异步，历史操作是简单 dict 操作，无锁竞争问题

## Migration Plan

1. 创建 `src/llm/client.py`（LLM 客户端）
2. 创建 `src/chat/`（service, history, prompt）
3. 创建 `src/web/`（FastAPI 应用）
4. 修改 `src/bot/handlers.py` 调用 ChatService
5. 修改 `src/main.py` 支持同时启动 Bot 和 FastAPI
6. 更新 `config.example.yaml` 和 `requirements.txt`
7. 测试：Telegram 发消息 + HTTP POST /api/chat 均正常

## Open Questions

1. **FastAPI 和 Telegram Bot 是否同进程运行？** — 建议 MVP 同进程（asyncio.gather），后续可拆分为独立服务
2. **LLM 层的 LangChain 依赖？** — MVP 直接用 OpenAI SDK（更轻量），LangChain 留给后续需要链式编排时引入

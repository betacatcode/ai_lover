## 1. LLM 接口层

- [x] 1.1 创建 `src/llm/__init__.py` 和 `src/llm/client.py`，实现 `LLMClient` 类（OpenAI SDK 封装，接收 messages 列表，返回文本）
- [x] 1.2 实现超时和错误处理（超时抛 `LLMTimeoutError`，API 错误抛 `LLMError`，不暴露 API Key）
- [x] 1.3 添加 `exceptions.py` 定义 LLM 层异常

## 2. 聊天业务层

- [x] 2.1 创建 `src/chat/__init__.py`，实现 `ChatService` 类（依赖注入 `LLMClient` + config）
- [x] 2.2 创建 `src/chat/history.py`，实现内存对话历史管理（滑动窗口，按 user_id 隔离）
- [x] 2.3 创建 `src/chat/prompt.py`，实现诺艾尔基础人设 Prompt 模板（Layer 1）和 system prompt 组装函数
- [x] 2.4 实现 `ChatService.chat(user_id, message) -> str`：加载历史 → 组装 Prompt → 调用 LLM → 保存历史 → 返回回复
- [x] 2.5 实现 LLM 失败时的降级回复（友好提示，不暴露技术细节）

## 3. FastAPI 应用层

- [x] 3.1 创建 `src/web/__init__.py` 和 `src/web/app.py`，实现 `create_app(chat_service)` 工厂函数
- [x] 3.2 实现 `POST /api/chat` 端点（请求: `{user_id, message}`，响应: `{reply, user_id}`）
- [x] 3.3 实现 `GET /api/health` 健康检查端点
- [x] 3.4 添加请求验证（缺少 message 返回 422）

## 4. 适配 Telegram Bot 到聊天服务

- [x] 4.1 修改 `src/bot/handlers.py`，将占位 echo 替换为调用 `ChatService.chat()`
- [x] 4.2 修改 `/status` 命令展示真实的好感度/情绪（当前为硬编码占位）
- [x] 4.3 修改 `/reset` 命令调用 `ChatService.reset_history()`

## 5. 主入口整合

- [x] 5.1 修改 `src/main.py`，支持通过命令行参数选择运行模式（`--mode bot|web|both`，默认 both）
- [x] 5.2 实现 `both` 模式下 `asyncio.gather` 同时运行 Bot 轮询和 FastAPI uvicorn
- [x] 5.3 在启动时初始化 `LLMClient` → `ChatService` → 注入到 Bot 和 Web

## 6. 配置与依赖

- [x] 6.1 更新 `config.example.yaml`，新增 `web` 段（host/port）
- [x] 6.2 更新 `requirements.txt`，添加 `fastapi>=0.110.0`, `uvicorn[standard]>=0.27.0`
- [x] 6.3 安装新依赖

## 7. 端到端测试

- [x] 7.1 启动服务（both 模式），确认 Bot 和 FastAPI 都正常启动
- [x] 7.2 通过 Telegram 发消息，确认收到诺艾尔回复（不再是 echo）
- [x] 7.3 通过 `curl POST /api/chat` 发消息，确认返回正确回复
- [x] 7.4 测试错误场景：停止 LongCat → 确认降级回复正常返回

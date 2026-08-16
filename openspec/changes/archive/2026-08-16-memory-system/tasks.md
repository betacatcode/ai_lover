## 1. 数据库表结构

- [x] 1.1 新增 `UserProfileModel`（user_id PK, facts JSONB, updated_at）
- [x] 1.2 新增 `ChatHistoryModel`（id PK, user_id, role, content, raw_content, emotion, affection_level, affection_points, created_at）
- [x] 1.3 新增 `ConversationSummaryModel`（id PK, user_id, content, embedding VECTOR(512), start_round, end_round, created_at）
- [x] 1.4 新增 pgvector 扩展和向量索引

## 2. Embedding 服务

- [x] 2.1 实现 `EmbeddingService` 类（加载 bge-small-zh-v1.5 模型）
- [x] 2.2 实现 `encode(text) → list[float]` 方法
- [x] 2.3 启动时预加载模型到内存

## 3. 对话历史持久化

- [x] 3.1 修改 `ChatHistoryManager`，新增 `PostgresHistoryRepository`
- [x] 3.2 每轮对话结束后异步写入 `chat_history` 表
- [x] 3.3 写入时附带状态快照（emotion, affection_level, affection_points）
- [x] 3.4 AI 回复同时存储 `content`（过滤后）和 `raw_content`（原始）
- [x] 3.5 服务启动时从 DB 加载最近 10 轮到内存滑动窗口

## 4. 用户画像系统

- [x] 4.1 实现 `ProfileExtractor`（LLM prompt 模板 + JSON 解析）
- [x] 4.2 实现 `ProfileRepository`（upsert 合并逻辑）
- [x] 4.3 实现 `build_profile_prompt_layer()` 函数（Layer 4）
- [x] 4.4 画像事实上限 10 条（按 updated_at 排序取最新）

## 5. 对话摘要系统

- [x] 5.1 实现 `SummaryGenerator`（LLM prompt 模板）
- [x] 5.2 实现 `SummaryRepository`（save + get_recent + search）
- [x] 5.3 摘要生成后调用 Embedding 并存入向量
- [x] 5.4 实现 `build_memory_prompt_layer()` 函数（Layer 5：最近 2 段 + 语义检索 Top-3）

## 6. 向量语义检索

- [x] 6.1 实现 `search(user_id, query_embedding, top_k=3)` 方法
- [x] 6.2 检索范围：conversation_summary + user_profile facts
- [x] 6.3 返回结果按相似度排序

## 7. 异步任务调度

- [x] 7.1 新增 `MemoryScheduler`（APScheduler，或复用现有 scheduler.py）
- [x] 7.2 每 10 轮对话后触发异步任务
- [x] 7.3 任务逻辑：读 DB 最近 10 轮 → 提取画像 → 生成摘要
- [x] 7.4 任务失败记录日志，不阻塞对话

## 8. Prompt 集成

- [x] 8.1 修改 `build_system_prompt()`，新增 `memory_state` 参数
- [x] 8.2 接入 Layer 4（画像）和 Layer 5（记忆）
- [x] 8.3 修改 `ChatService.chat()` 调用 memory 相关逻辑

## 9. 配置

- [x] 9.1 `config.py` 新增 `memory_trigger_rounds = 10`
- [x] 9.2 `config.yaml` 新增记忆相关配置
- [x] 9.3 Embedding 模型配置更新为 bge-small-zh-v1.5

## 10. 测试

- [x] 10.1 单元测试：EmbeddingService 编码/解码
- [x] 10.2 单元测试：ProfileExtractor 解析
- [x] 10.3 单元测试：SummaryGenerator 生成
- [ ] 10.4 单元测试：向量检索 pgvector（需要真实 DB 环境）
- [ ] 10.5 集成测试：完整对话流程（10 轮触发画像+摘要）
- [ ] 10.6 集成测试：服务重启后记忆恢复

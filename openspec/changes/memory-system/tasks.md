## 1. 数据库初始化

- [ ] 1.1 实现 PostgreSQL 表结构（user_profile、chat_history、summary，含 pgvector 向量列）
- [ ] 1.2 实现数据库初始化脚本

## 2. 用户画像

- [ ] 2.1 实现用户画像提取和存储（从对话中提取结构化事实）
- [ ] 2.2 实现用户画像 → Prompt 注入（Layer 4）

## 3. 对话历史与摘要

- [ ] 3.1 实现对话历史持久化（每轮对话存入 PostgreSQL）
- [ ] 3.2 实现对话摘要生成（超阈值时调用 LLM 压缩早期对话）
- [ ] 3.3 实现摘要 → Prompt 注入（Layer 5）

## 4. 向量检索

- [ ] 4.1 实现 embedding 生成（sentence-transformers 本地模型）
- [ ] 4.2 实现 pgvector 语义检索接口

## 5. 测试

- [ ] 5.1 端到端测试：记忆持久化、摘要生成、向量检索均正常工作

## Context

长期记忆是诺艾尔持续了解用户的基础。项目已选用 PostgreSQL + pgvector 作为存储方案（Decision 5），需实现表结构和向量检索。

## Goals / Non-Goals

**Goals:**
- 用户画像提取和存储（结构化事实）
- 对话历史持久化
- 超阈值时 LLM 摘要压缩
- pgvector 向量语义检索
- 记忆 → Prompt 注入（Layer 4 + 5）

**Non-Goals:**
- MVP 阶段摘要触发阈值固定（30轮），后续可调

## Decisions

### Decision 1: 向量生成

使用 sentence-transformers 本地模型（paraphrase-multilingual-MiniLM-L12-v2, 384维），因为 LongCat 不支持 embedding API。

**Why**: 本地生成无需额外 API，支持中文。

## Risks / Trade-offs

### Risk: Prompt 过长
- **Mitigation**: 控制注入量（画像最多 10 条、摘要最多 3 段、对话最多 15 轮），设置 token 上限

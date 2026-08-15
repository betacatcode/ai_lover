## Context

这是一个全新的 Python 项目，无既有代码。项目目标是构建一个 Telegram 上的 AI 女友 Bot，人设是原神中的女仆诺艾尔。MVP 阶段聚焦多轮文本对话，但架构上需要为后续的情感系统、自主行为、图片理解留好扩展空间。

技术约束：
- 单一用户（开发者本人），无需多租户
- 本地开发，部署到自有云服务器
- LLM 通过 LongCat 代理（OpenAI 兼容 API）
- 使用 LangChain 作为 LLM 编排框架

## Goals / Non-Goals

**Goals:**
- 实现诺艾尔人设驱动的多轮文本对话
- 实现动态 Prompt 组装（人设 + 记忆 + 好感度 + 情绪 + 对话历史）
- 实现好感度系统（5 阶段制，影响称呼和行为）
- 实现情绪系统（6 种状态，自然衰减）
- 实现长期记忆（用户画像 + 对话摘要）
- 架构上预留自主行为引擎和图片理解的扩展点

**Non-Goals (MVP):**
- 自主行为引擎的具体实现（定时浏览社交媒体）
- 图片理解功能
- 语音功能
- 多用户支持
- Web 管理界面

## Decisions

### Decision 1: Telegram Bot 框架选择 aiogram

**选择 aiogram 而非 python-telegram-bot。**

- **Why**: aiogram 基于 asyncio，原生支持异步。后续自主行为引擎需要定时任务调度，异步模型天然适配。python-telegram-bot 虽然上手更简单，但同步模型在加入定时任务后需要额外处理。
- **Alternatives**: python-telegram-bot（更成熟但同步）、Telethon（更底层但需要更多样板代码）。

### Decision 2: LLM 调用通过 LangChain 编排

**使用 LangChain 作为 LLM 调用和 Prompt 编排的框架。**

- **Why**: LangChain 提供标准化的 ChatPromptTemplate、Memory、Chain 抽象，非常适合动态 Prompt 组装场景。后续扩展（记忆检索、摘要压缩、多 Chain 协作）都有现成组件。通过 OpenAI SDK 兼容接口连接 LongCat。
- **Alternatives**: 直接调用 OpenAI SDK（更简单但后续扩展需要自己实现编排逻辑）。

### Decision 3: 动态 Prompt 组装架构

**每次对话实时组装 system prompt，而非使用静态 prompt。**

组装结构（按优先级从高到低）：

```
┌──────────────────────────────────────────────────┐
│ System Prompt (每次实时组装)                       │
├──────────────────────────────────────────────────┤
│ Layer 1: 基础人设 (静态文本，定义诺艾尔核心性格)     │
│ Layer 2: 好感度状态 (当前等级 → 称呼 + 行为指令)     │
│ Layer 3: 情绪状态 (当前情绪 → 语气风格指令)          │
│ Layer 4: 长期记忆 (用户画像事实 + 相关记忆片段)      │
│ Layer 5: 对话摘要 (早期对话的压缩摘要)               │
├──────────────────────────────────────────────────┤
│ Messages (最近 N 轮对话原文)                       │
│ [user, assistant, user, assistant, ...]          │
│ + 当前用户输入                                     │
└──────────────────────────────────────────────────┘
```

- **Why**: 静态 prompt 无法体现好感度变化、情绪波动和记忆积累。实时组装让每次对话都基于最新状态。
- **Alternatives**: 静态 prompt + 定期全量更新（无法做到每轮精细控制）。

### Decision 4: 好感度与情绪独立维护

**好感度（长期变量）和情绪（短期变量）作为独立系统，分别持久化，共同注入 Prompt。**

- **Why**: 好感度变化慢（天/周级别），代表关系深度；情绪变化快（分钟/小时级别），代表当下状态。两者独立才能表达"关系很好但此刻她很难过"这种复杂状态。
- **Alternatives**: 合并为一个"关系值"（无法区分长期关系和短期情绪）。

### Decision 5: 存储方案用 PostgreSQL + pgvector

**使用 PostgreSQL（含 pgvector 扩展）作为统一存储：关系数据 + 向量检索。**

- **Why**:
  - 用户偏好 PostgreSQL，部署自有云服务器，PG 运维成本可接受。
  - pgvector 扩展提供向量检索能力，用于记忆碎片的语义检索（对话历史、用户画像、自主行为产生的内容），避免全量注入 prompt 导致的 token 膨胀。
  - 一个数据库同时解决关系存储和向量检索，无需额外服务（Chroma/FAISS 等），运维最简单。
  - 后续记忆量增长时，向量检索质量不降级。
- **Alternatives**:
  - SQLite（零配置但无向量能力，后续需迁移）。
  - SQLite + 独立向量库（如 Chroma）（多一个服务，运维复杂度增加）。
  - pgvector 也可在云端用 Supabase / Neon 等托管 PG 服务，进一步降低运维。

**数据存储分工：**

| 数据类型 | 存储方式 | 说明 |
|---------|---------|------|
| 好感度 / 情绪状态 | PG 关系表 | 单行记录，频繁更新 |
| 对话原文 | PG 关系表 | 持久化，用于后续摘要 |
| 对话摘要 | PG 关系表 + 向量 | 摘要文本 + embedding，语义检索 |
| 用户画像事实 | PG 关系表 + 向量 | 结构化事实 + embedding，语义检索 |
| 自主行为记忆 | 向量为主 | 浏览内容的碎片化记忆 |

### Decision 6: 对话摘要策略

**当对话超过阈值轮数时，用 LLM 对早期对话生成结构化摘要。**

摘要包含：主要话题、用户表达的重要信息、诺艾尔做出的约定、用户情绪变化。

- **Why**: 直接截断丢失信息，全部塞入浪费 token。LLM 摘要能在压缩率和信息保留间取得平衡。
- **Alternatives**: 固定窗口截断（丢失早期信息）、全部存入向量库检索（MVP 阶段过重）。

### Decision 7: 自主行为引擎的架构预留

**MVP 不实现自主行为，但代码结构上预留 Scheduler 模块接口。**

- **Why**: 自主行为是核心差异化能力，但 MVP 先验证对话体验。预留接口避免后续重构。
- **设计**: 定义 `AutonomousBehavior` 接口，MVP 阶段为空实现，后续接入 APScheduler + 内容抓取。

## Risks / Trade-offs

### Risk: Prompt 过长导致 token 消耗过大
- **Mitigation**: 控制各层记忆注入量（画像最多 10 条、摘要最多 3 段、对话原文最多 15 轮）。设置 token 上限，超出时优先裁剪对话原文。

### Risk: 好感度/情绪系统让回复变得不自然
- **Mitigation**: 好感度和情绪以"软指令"形式注入（如"当前心情不错，语气轻松"），而非硬规则。通过 prompt 调优找到平衡点。

### Risk: LongCat API 的稳定性和延迟
- **Mitigation**: 实现超时重试机制，超时后返回友好提示。考虑后续支持多模型 fallback。

### Risk: 诺艾尔人设漂移（长时间对话后不像诺艾尔）
- **Mitigation**: 基础人设 prompt 要足够强（含大量示例对话），好感度和情绪只影响语气不影响核心性格。

### Trade-off: 实时组装 Prompt vs 性能
- 每次对话都组装 prompt 增加少量延迟，但换来状态一致性。可接受。

## Migration Plan

### 部署步骤
1. 本地开发调试通过
2. 云服务器安装 Python 环境
3. 上传代码 + 配置环境变量（Telegram Bot Token、LongCat API Key）
4. 使用 systemd 或 supervisor 守护进程运行
5. 配置日志轮转

### 数据迁移
- MVP 阶段无既有数据，无需迁移
- 后续版本升级时，SQLite schema 变更通过 migration 脚本处理

## Open Questions

1. **LongCat 的具体 API base URL 和模型名称** — 需要用户配置时确认
2. **社交媒体抓取的具体源列表** — 自主行为阶段再确定（贴吧哪些板块、哪些论坛）
3. **对话摘要的触发阈值** — 建议 30 轮，但需根据实际 token 消耗调优
4. **好感度变化的数值粒度** — 建议用整数点数 + 阶段阈值，具体数值需调优
5. **Embedding 模型选择** — pgvector 需要生成向量，MVP 阶段可用 LongCat 若支持 embedding 接口，否则用 sentence-transformers 本地模型

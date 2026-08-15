## Context

好感度系统是诺艾尔与用户关系的核心变量（长期，天/周级别）。当前代码尚未实现此系统，Prompt 组装器需要扩展 Layer 2 来注入好感度状态。

## Goals / Non-Goals

**Goals:**
- 5 阶段好感度模型（陌生/认识/信赖/亲密/伴侣）
- 好感度持久化到 PostgreSQL
- 根据对话内容动态调整好感度
- 好感度 → Prompt 注入（称呼 + 行为指令）

**Non-Goals:**
- 不影响情绪系统（独立维护）
- MVP 阶段不实现复杂的对话分析（用简单规则）

## Decisions

### Decision 1: 好感度存储

使用 PostgreSQL 单行记录（user_id, level, points, updated_at）。

**Why**: 与项目存储方案一致，无需额外服务。

### Decision 2: 好感度变化规则

基于关键词匹配 + 频率统计的简单规则（MVP），后续可升级为 LLM 分析。

**Why**: MVP 先验证机制，LLM 分析留给后续迭代。

## Risks / Trade-offs

### Risk: 好感度变化不自然
- **Mitigation**: 设置单次变化上限，避免单条消息大幅波动

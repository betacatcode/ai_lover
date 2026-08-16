## Context

情绪系统是诺艾尔的短期状态变量（分钟/小时级别），与好感度独立。当前代码尚未实现，Prompt 组装器需要 Layer 3。

## Goals / Non-Goals

**Goals:**
- 6 种情绪状态（开心/担心/寂寞/难过/生气/平静）
- 基于对话内容触发情绪变化
- 非平静情绪随时间自然衰减
- 情绪 → Prompt 注入（语气风格指令）

**Non-Goals:**
- 不影响好感度系统
- MVP 用关键词匹配触发（后续可升级 LLM 分析）

## Decisions

### Decision 1: 情绪衰减

使用 APScheduler 定时检查，非平静情绪按时间衰减。

**Why**: 项目已计划使用 APScheduler，天然适配。

## Risks / Trade-offs

### Risk: 情绪变化过于频繁
- **Mitigation**: 设置情绪冷却期，避免连续切换

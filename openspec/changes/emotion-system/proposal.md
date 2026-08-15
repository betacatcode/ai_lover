## Why

情绪系统让诺艾尔有短期状态变化（开心/担心/寂寞/难过/生气/平静），与好感度（长期关系）独立，共同塑造立体的角色性格。

## What Changes

- 新增情绪数据模型（6 种状态）
- 实现情绪存储（PostgreSQL）
- 实现情绪 → Prompt 注入（Layer 3）
- 实现情绪触发逻辑
- 实现情绪自然衰减（定时任务向平静衰减）

## Capabilities

### New Capabilities

- `emotion`: 情绪系统，6 种状态、触发逻辑、自然衰减、Prompt 注入

## Impact

- 代码: 新增 `src/systems/emotion.py`
- 数据库: 新增 `emotion` 表
- Prompt: 新增 Layer 3（情绪语气风格指令）
- 调度: APScheduler 定时衰减任务

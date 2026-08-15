## Why

诺艾尔与用户的关系亲密度是 AI 女友体验的核心差异化能力。好感度系统让诺艾尔能感知关系深度，动态调整称呼和行为模式，使对话更自然、有成长感。

## What Changes

- 新增好感度数据模型（5 阶段枚举）
- 实现好感度存储（PostgreSQL）
- 实现好感度 → Prompt 注入（Layer 2）
- 实现好感度变化逻辑（分析对话内容增减经验值）
- 好感度阶段变化时的特殊处理（改口过渡）

## Capabilities

### New Capabilities

- `affection`: 好感度系统，定义 5 阶段关系模型、变化规则、Prompt 注入

## Impact

- 代码: 新增 `src/systems/affection.py`
- 数据库: 新增 `affection` 表
- Prompt: 新增 Layer 2（好感度状态注入）

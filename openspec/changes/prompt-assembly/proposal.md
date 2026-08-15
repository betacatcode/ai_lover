## Why

动态 Prompt 组装器是整合所有系统（好感度、情绪、记忆、摘要）的核心组件，按 Layer 1-5 顺序拼接 system prompt，控制 token 上限。

## What Changes

- 实现 Prompt 组装器（按 Layer 1-5 顺序拼接）
- 实现 token 估算和裁剪逻辑
- 整合所有系统到完整对话处理管线

## Capabilities

### New Capabilities

- `prompt-assembly`: 动态 Prompt 组装器，Layer 1-5 拼接、token 控制

## Impact

- 代码: 重构 `src/chat/prompt.py` 为完整组装器
- 依赖: 好感度、情绪、记忆系统完成后才能完整集成

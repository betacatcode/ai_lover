## Why

自主行为引擎是核心差异化能力——诺艾尔能主动浏览社交媒体、产生记忆、主动发起对话。MVP 阶段预留接口，后续实现。

## What Changes

- 定义 AutonomousBehavior 接口和空实现
- 实现 APScheduler 定时任务框架
- 实现内容抓取、理解、记忆转化、主动对话触发

## Capabilities

### New Capabilities

- `autonomous-behavior`: 自主行为引擎，定时浏览、内容抓取、主动对话

## Impact

- 代码: 新增 `src/autonomous/`
- 依赖: APScheduler（已在 requirements.txt 中）

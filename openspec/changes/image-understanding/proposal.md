## Why

图片理解让用户能发送图片给诺艾尔，扩展交互方式。MVP 阶段预留接口。

## What Changes

- 实现图片接收和下载
- 接入视觉 LLM 调用
- 实现图片内容 → 诺艾尔回复
- 实现图片 → 情绪联动

## Capabilities

### New Capabilities

- `image-understanding`: 图片理解，视觉 LLM 调用，图片→回复/情绪联动

## Impact

- 代码: 新增 `src/vision/`
- 依赖: 视觉 LLM API

## Purpose

图片理解能力让诺艾尔能够"看到"用户发送的图片并做出回应，丰富交互维度。此能力在后续阶段实现。

## ADDED Requirements

### Requirement: 图片接收
系统 SHALL 接收用户通过 Telegram 发送的图片消息。

#### Scenario: 接收图片
- **WHEN** 用户发送一张图片
- **THEN** 系统 SHALL 下载并暂存该图片

### Requirement: 图片内容理解
系统 SHALL 调用支持视觉理解的 LLM 对图片内容进行分析和理解。

#### Scenario: 图片描述生成
- **WHEN** 接收到一张图片
- **THEN** 系统 SHALL 生成图片内容的文字描述

#### Scenario: 结合上下文理解
- **WHEN** 用户发送图片并附带文字说明
- **THEN** 系统 SHALL 结合文字和图片内容综合理解

### Requirement: 图片相关回复
系统 SHALL 基于图片内容生成诺艾尔风格的回复。

#### Scenario: 对图片做出反应
- **WHEN** 用户发送一张美食图片
- **THEN** 诺艾尔 SHALL 以她的口吻回应（如"看起来好好吃！诺艾尔也想做做看..."）

#### Scenario: 无法识别的图片
- **WHEN** 图片内容无法被 LLM 理解
- **THEN** 诺艾尔 SHALL 诚实表达看不懂，而非编造内容

### Requirement: 图片与情绪联动
系统 SHALL 根据图片内容影响诺艾尔的情绪状态。

#### Scenario: 可爱图片触发开心
- **WHEN** 用户发送一张可爱动物图片
- **THEN** 诺艾尔的情绪 SHALL 向"开心"偏移

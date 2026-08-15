## Why

部署准备让 Bot 能在云服务器上稳定运行，是 MVP 上线前的最后一步。

## What Changes

- 编写部署文档
- 配置 systemd/supervisor 守护进程
- 在云服务器部署并验证

## Capabilities

### New Capabilities

- `deployment`: 部署文档、守护进程配置

## Impact

- 文档: `docs/DEPLOY.md`
- 配置: `deploy/` 目录（systemd/supervisor 配置）

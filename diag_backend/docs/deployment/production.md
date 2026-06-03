# 生产部署

## 推荐架构

```
[Nginx] → [Uvicorn workers] → MongoDB
                ↓
         内网 MES / FTP / RAGFlow / LLM
```

## Uvicorn

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

::: warning
多 worker 时每个进程各启 Analytics + Sync 调度器，可能 **重复** 跑定时任务。生产建议：
- 单 worker + 足够 async 并发，或
- 调度器拆独立进程（当前未实现）
:::

## 环境变量

生产通过 systemd/K8s 注入，见 [环境变量](/deployment/environment-vars)。

## 反向代理

- 终止 TLS
- `proxy_read_timeout` ≥ 120s（SSE 诊断）
- WebSocket 非必需（SSE 用 HTTP）

## 静态资源

后端不提供前端静态文件；前端独立部署 Vite build。

## 文档站构建

```bash
cd diag_backend/docs
npm run docs:build
# 输出 .vitepress/dist，可挂 Nginx /docs-backend/
```

## 健康检查

`GET /health` — 可接 K8s liveness（不查 MongoDB）。

## 日志

配置 `LOG_FILE` + 集中采集（JSON 格式 `LOG_JSON=true`）。

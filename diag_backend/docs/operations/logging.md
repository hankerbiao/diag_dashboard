# 日志与监控

## 应用日志

配置见 [日志模块](/core/logger)。

### 关键 event（extra）

lifespan 使用 `event` 字段：`app_startup`, `mongodb_connected`, `analytics_scheduler_started`, `app_shutdown`

### 请求中间件

每条 HTTP：method, path, status, duration ms

### 业务日志级别建议

| 场景 | 级别 |
|------|------|
| MES 失败 | WARNING + DEBUG detail |
| 聚合失败 | ERROR |
| 同步完成 | INFO |
| LLM 调用 | INFO（勿 log 完整 prompt 含 secret） |

## sync_jobs.progress

UI 读 stdout 尾部，非结构化；排障也可直接 SSH 看 scripts 输出。

## MongoDB 监控

- 慢查询 log
- 连接数
- 磁盘（test_details 增长快）

## 指标（未内置）

可接 Prometheus：

- `/health` uptime
- 自定义 middleware 计数 5xx
- sync_jobs failed 计数

## 文档

- 后端 Swagger：`/docs`
- 本文档站：`npm run docs:dev`

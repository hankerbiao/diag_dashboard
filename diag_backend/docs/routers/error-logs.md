# 异常日志路由 (error-logs)

**文件：** `app/routers/error_logs.py`

Prefix: `/api/error-logs`

由 `ErrorLogsService` 提供聚合统计。

| 端点 | 说明 |
|------|------|
| GET `/stats` | 异常统计 |
| GET `/trend` | 时间趋势 |
| GET `/stats/yield` | 良率 |

::: tip
前端异常看板主列表数据来自 **`/api/sync/servers`** 与 **`/api/sync/servers/{sn}/test-details`**，智能剖析走 **`/api/diagnosis/error-log/*`**。
:::

详见 [ErrorLogsService](/services/error-logs-service)。

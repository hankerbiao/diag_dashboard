# 异常日志服务

**文件：** `app/services/error_logs_service.py`

## 职责

为 `/api/error-logs/*` 提供统计数据（聚合 `error_logs` 或 sync 集合，视实现版本而定）。

## 单例

`get_error_logs_service()`

## 与看板区别

| 模块 | 数据源 | 用途 |
|------|--------|------|
| ErrorLogsService | error_logs 等 | 旧版统计 API |
| AnalyticsService | sync_remote_test_details | 批次测试看板 |
| SyncService | sync_remote_* | 异常看板列表/详情 |

前端「异常看板」主路径已以 **sync + analytics + diagnosis** 为主。

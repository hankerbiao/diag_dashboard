# 日志

**文件：** `app/core/logger.py`

在 `app/main.py` 启动时调用 `setup_logging()`。

## 配置项

| 变量 | 效果 |
|------|------|
| `LOG_LEVEL` | 根 logger 级别 |
| `LOG_FORMAT` | `console` 人类可读 / `json` 结构化 |
| `LOG_FILE` | 启用 RotatingFileHandler |
| `LOG_MAX_BYTES` / `LOG_BACKUP_COUNT` | 轮转 |
| `LOG_JSON` | JSON 行格式 |

## 中间件

`app/middleware/logging.py` 记录每个 HTTP 请求：

- method, path, status, duration

## 业务日志约定

- 模块：`logger = logging.getLogger(__name__)`
- MES 失败：`logger.warning` + `logger.debug` 带 request debug JSON
- 聚合失败：`analytics_service` `logging.error`
- 同步脚本：`sync_jobs.progress` 存 stdout  tail

## 同步脚本日志

`diag_backend/logs/sync_YYYYMMDD.log` — 由 scripts 写入，非 core logger。

详见 [日志与监控](/operations/logging)。

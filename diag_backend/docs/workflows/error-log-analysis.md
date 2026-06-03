# 异常日志智能剖析

## 触发

异常看板测试详情 →「智能剖析」→ `POST /api/diagnosis/error-log/{id}/analyze`（SSE）。

## error_log_id 解析

1. **ObjectId** — 直接查 MongoDB
2. **合成 ID** — `{factory}_{sn}_{test_time}_{idx}`，解析后查 sync 集合或 MES

## ErrorLogAnalyzeContext

前端 POST body 携带行上下文（factory_id, server_sn, test_time, log_path, fault_types...），当 MES 返回空 `server_sn` 时仍可剖析。

## SSE 三阶段

`download` → `ragflow` → `llm`

结果 upsert `diagnosis_cache`（key: `error_log_id`）。

## 「未找到异常日志」 vs 「FTP 失败」

| 消息 | 阶段 |
|------|------|
| 未找到异常日志 | 记录 lookup 失败（MES/ID） |
| 日志下载失败 / 550 | download 阶段 URL/FTP 问题 |

## 重新分析

`POST .../re-analyze` 忽略 cache 重跑全流程。

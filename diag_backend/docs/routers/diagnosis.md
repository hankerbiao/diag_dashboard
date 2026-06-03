# 诊断路由 (diagnosis)

**文件：** `app/routers/diagnosis.py`（核心模块，~1400 行）

Prefix: `/api/diagnosis`  
认证: 全部 `Depends(get_current_user)`

## SN 诊断 POST /sn

**Body:** `DiagnosisBySNRequest`

```json
{
  "sn": "SN123456",
  "factory": "kunshan",
  "stream": false
}
```

### 非流式

返回 `DiagnosisResponse`：根因、证据、维修建议、引用数据等。

### 流式 (stream=true)

`StreamingResponse` SSE 事件：

| event | 含义 |
|-------|------|
| `progress` | `{ stage, detail }` device/sims/logfiles/cases/ragflow/llm |
| `result` | 完整诊断 JSON |
| `error` | 错误信息 |

### 数据收集 `_gather_sn_data`

1. `knowledge_graph.get_device_by_sn`
2. `MESDirectService.get_test_details` — SIMS 实时
3. 筛选失败项，下载日志（HTTP/FTP，`MAX_LOG_BYTES` 2MB）
4. `knowledge_graph` — 案例库、维修记录
5. `ragflow_service.search_knowledge_base`
6. 组装 prompt → `llm_service`

SIMS 失败抛出 `ValueError`，前端显示友好提示。

## 日志内容 POST /sn/log-content

**Query/Body:** `sn`, `factory`, `log_path`

- `validate_log_path` + `build_log_download_url`
- HTTP: httpx；FTP: urllib 匿名或带凭据
- 返回 `{ content, truncated, lines }`

异常看板「下载日志」按钮走此 API。

## 异常日志分析

### ID 格式

- MongoDB ObjectId
- 或合成 ID：`{factory}_{sn}_{test_time}_{idx}`

`_get_error_log_detail` 多级回退：Mongo → MES 重拉。

### POST /error-log/:id/analyze (SSE)

**Body 可选:** `ErrorLogAnalyzeContext` — 前端行上下文，避免 MES 空 `server_sn`。

阶段：`download` → `ragflow` → `llm`

结果写入 `diagnosis_cache`（`error_log_id` unique）。

### POST /error-log/:id/re-analyze

忽略 cache，强制重跑管道。

## SN 历史

| 端点 | 集合 |
|------|------|
| save-history | `diagnosis_sn_history` insert |
| history list/detail | 按 `sn` / `user_id` 查询 |
| append chat | `$push` chat_messages |

## 常量

```python
MAX_LOG_BYTES = 2 * 1024 * 1024
LOG_TAIL_LINES = 50
RAG_TOP_K = 10
```

## 相关文档

- [SN 诊断工作流](/workflows/sn-diagnosis)
- [异常日志剖析](/workflows/error-log-analysis)
- [日志下载](/workflows/log-download)

## 测试

`tests/test_diagnosis_routes.py`, `test_error_log_detail_lookup.py`, `test_log_download.py`

# 故障排查

## QueryPlanKilled (code 175)

**日志：**

```
Aggregation failed: ... index 'idx_sync_servers_sn' ... dropped
```

**原因：** 启动时 drop 索引 + 聚合并发（reload/多实例）。

**修复：** 已改为仅 legacy unique 索引才 drop；聚合自动重试。仍出现则检查是否多实例同时重启。

---

## MES 502 / SIMS 查询失败

**现象：** 诊断「SIMS 查询失败 [大同厂区]」

**原因：** 厂区 `base_url` 对应 MES 宕机（非 WeaveEye bug）。

**处理：** 检查 `configs/factories.yaml` `base_url`，curl 探测，联系厂区 infra。

---

## 未找到异常日志

**阶段：** 记录 lookup，在日志 download 之前。

**常见原因：**

- MES 502 导致无法补拉
- error_log_id 格式错误
- 前端未传 `ErrorLogAnalyzeContext`

**处理：** 传 AnalyzeContext；查 `diagnosis.py` `_get_error_log_detail` 日志。

---

## FTP 日志下载失败 / 550

**阶段：** download。

**原因：** URL 路径错误、FTP 需认证、网络不通。

**处理：** 见 [日志下载](/workflows/log-download)；检查 `/log//` 前缀与 YAML 凭据。

---

## 看板数据为空

1. 是否跑过 `sync_data.py`
2. `sync_remote_test_details.test_time` 是否在 `days` 窗口内
3. `analytics_snapshots` 是否有文档
4. 手动 `GET /analytics/insights?factory_id=...`

---

## JWT 401

- Token 过期
- JWT_SECRET_KEY 变更导致旧 token 失效
- 未带 `Authorization: Bearer`

---

## RAGFlow 不可用

知识库上传仍 OK；诊断 ragflow 阶段跳过。查 `GET /knowledge-base/ragflow/status`。

---

## 同步任务 stuck running

查 `sync_jobs` 对应文档；kill  orphan subprocess；手动改 status 或等超时（脚本 1h wait_for 保护在 scheduler 层）。

---

## 联系

产线操作问题：光圈联系 libiao1（与前端 SupportHint 一致）。

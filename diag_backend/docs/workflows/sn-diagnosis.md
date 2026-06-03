# SN 单机诊断工作流

## 触发

前端 DiagnosisTab → `POST /api/diagnosis/sn`（可选 `stream: true`）。

## 阶段

| stage | 动作 |
|-------|------|
| device | MongoDB `devices` |
| sims | MESDirectService 实时测试列表 |
| logfiles | 失败项日志 HTTP/FTP 下载 |
| cases | case_library + maintenance |
| ragflow | 向量检索（可选） |
| llm | 生成 DiagnosisResponse |

## 失败模式

| 用户可见 | 后端原因 |
|----------|----------|
| SIMS 查询失败 | MES 502/超时/SN 错误 |
| 日志为空 | 无失败项或 log 字段空 |
| LLM 失败 | API Key/配额/超时 |

## 历史

诊断完成后可 `save-history` → `diagnosis_sn_history`，支持 follow-up chat。

## 相关代码

- `diagnosis.py` — `_gather_sn_data`, `_diagnose_sn`
- `llm_service.py` — prompt + API
- [诊断路由](/routers/diagnosis)

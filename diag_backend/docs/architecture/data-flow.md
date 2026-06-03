# 数据流

## SN 诊断数据流

```mermaid
flowchart LR
  A[POST /diagnosis/sn] --> B[knowledge_graph.get_device_by_sn]
  A --> C[MESDirectService.get_test_details]
  C --> D[下载失败日志 FTP/HTTP]
  B --> E[knowledge_graph 案例/维修]
  D --> F[ragflow_service.search]
  E --> F
  F --> G[llm_service.diagnose]
  G --> H[DiagnosisResponse]
  H --> I[可选 save-history]
```

## 异常日志智能剖析

```mermaid
flowchart LR
  A[POST error-log/id/analyze SSE] --> B[解析 error_log_id 或 AnalyzeContext]
  B --> C[Mongo / MES 取记录]
  C --> D[下载 log_path]
  D --> E[RAG 检索]
  E --> F[LLM 分析]
  F --> G[diagnosis_cache upsert]
```

前端可 POST `ErrorLogAnalyzeContext`，避免 MES 二次查询失败。

## 厂区 SIMS 同步

```mermaid
flowchart TB
  T[定时/手动 trigger] --> J[sync_jobs insert running]
  J --> P[subprocess sync_data.py]
  P --> M[(sync_remote_servers)]
  P --> D[(sync_remote_test_details)]
  J --> U[更新 progress/status]
```

## 看板 insights

```mermaid
flowchart LR
  Q[GET /analytics/insights] --> K{有 search 参数?}
  K -->|是| C[实时 _compute]
  K -->|否| S[读 analytics_snapshots]
  S -->|miss| C
  C --> AGG[MongoDB aggregation]
  AGG --> R[返回 JSON]
  BG[AnalyticsService 每小时] --> AGG
  BG --> SN[写 snapshot]
```

## 知识库上传

1. `POST /knowledge-base/documents` multipart
2. 写本地 `data/knowledge_base/`
3. 写 `knowledge_documents` 元数据
4. 若 RAGFlow 可用：upload → parse → 更新 status

## 认证流

```
register/login → users 集合 → JWT
后续请求 Authorization: Bearer → get_current_user → 解码 email → 查 users
```

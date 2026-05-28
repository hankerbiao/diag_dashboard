# 数据流

## 认证流程

```
LoginPage                    Backend                    MongoDB
    │                          │                          │
    │ POST /api/auth/login     │                          │
    │ {email, password}        │                          │
    │─────────────────────────▶│                          │
    │                          │── find user by email ──▶│
    │                          │◀── user doc ────────────│
    │                          │                          │
    │                          │── verify password ──────│  (passlib bcrypt)
    │                          │                          │
    │                          │── sign JWT ─────────────│  (python-jose, HS256)
    │                          │                          │
    │◀── {access_token} ──────│                          │
    │                          │                          │
    │ 存 localStorage          │                          │
    │ 后续请求带 Authorization │                          │
    │── fetchApi() ──────────▶│                          │
    │                          │── decode JWT ───────────│
    │                          │── get_current_user ─────│
    │                          │                          │
```

## 诊断分析流程

```
Frontend                    Backend                     Storage/External
   │                           │                           │
   │ POST /analyze?log_base_url│                           │
   │──────────────────────────▶│                           │
   │                           │── check diagnosis_cache▶│ MongoDB
   │                           │◀── cache hit/miss ──────│
   │                           │                           │
   │ event:progress(download)  │                           │
   │◀──────────────────────────│                           │
   │                           │── _get_error_log_detail▶│ MongoDB
   │                           │                           │
   │                           │── _download_log_tail() ▶│ MES 日志服务器
   │                           │    httpx.AsyncClient     │ (log_base_url)
   │                           │    (2MB截断/HTML解析)    │
   │                           │                           │
   │ event:progress(ragflow)   │                           │
   │◀──────────────────────────│                           │
   │                           │── search_knowledge_base▶│ RAGFlow API
   │                           │    (top_k=10, 按doc去重)│ /api/v1/retrieval
   │                           │                           │
   │ event:progress(llm)       │                           │
   │ event:token(text)         │                           │
   │◀──────────────────────────│                           │
   │                           │── analyze_with_knowledge │ LLM API
   │                           │    _stream()             │ (OpenAI/Gemini)
   │                           │    (流式chat completion) │
   │                           │                           │
   │                           │── save diagnosis_cache ▶│ MongoDB
   │                           │                           │
   │ event:done({result})     │                           │
   │◀──────────────────────────│                           │
```

## 厂区数据同步流程

```
同步脚本 (scripts/sync_data.py)         MES API                    MongoDB
   │                                      │                          │
   │ for each factory in factories.yaml   │                          │
   │─────────────────────────────────────▶│                          │
   │                                      │                          │
   │── queryTestingServers.action ──────▶│ (分页拉取服务器列表)     │
   │◀── servers list ────────────────────│                          │
   │                                      │                          │
   │── upsert to sync_remote_servers ───▶│ (去重写入)               │
   │                                      │                          │
   │── queryTestList.action ────────────▶│ (按 SN 拉取测试明细)     │
   │◀── test details ────────────────────│                          │
   │                                      │                          │
   │── upsert to sync_remote_test_det ──▶│ (去重写入)               │
   │                                      │                          │
   │── log to sync_jobs ────────────────▶│ (记录同步状态)           │
   │                                      │                          │
```

## 看板数据流

```
AnalyticsService              MongoDB                       Frontend
   │                             │                             │
   │ _scheduler_loop()          │                             │
   │ (每小时执行)                │                             │
   │                             │                             │
   │── compute insights ──────▶│ sync_remote_servers         │
   │                            │ sync_remote_test_details    │
   │                             │                             │
   │── save to analytics_snap ▶│ (缓存: 趋势:天:厂区)        │
   │                             │                             │
   │                             │                             │
   │                             │                             │
   │ (用户请求 /api/analytics/insights)                      │
   │                             │◀───────────────────────────│
   │                             │                             │
   │ 无过滤器 → 读取快照 ──────▶│                             │
   │ 有过滤器 → 实时聚合 ──────▶│ (asyncio.gather × 6 pipes) │
   │                             │                             │
   │                             │── response ───────────────▶│
```

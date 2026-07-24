# 路由总览

所有路由在 `app/main.py` 注册，统一前缀 **`/api`**。

| 模块 | Prefix | 文件 | 需登录 |
|------|--------|------|--------|
| 认证 | `/auth` | `auth.py` | 部分 |
| 诊断 | `/diagnosis` | `diagnosis.py` | 是 |
| 异常日志 | `/error-logs` | `error_logs.py` | 是 |
| 分析 | `/analytics` | `analytics.py` | 是 |
| 同步 | `/sync` | `sync.py` | 是 |
| 知识库 | `/knowledge-base` | `knowledge_base.py` | 是 |
| 设置 | `/settings` | `settings.py` | 是 |
| 厂区 | `/factories` | `factories.py` | 是 |

## 端点速查

### Auth

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/auth/oa/callback` | OA 回调换取应用 JWT |
| GET | `/api/auth/me` | 当前 OA 用户 |
| GET | `/api/auth/me` | 当前用户 |

### Diagnosis

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/diagnosis/sn` | SN 诊断（JSON 或 SSE） |
| POST | `/api/diagnosis/sn/follow-up` | 追问聊天 |
| POST | `/api/diagnosis/sn/log-content` | 下载日志正文 |
| POST | `/api/diagnosis/error-log/{id}` | 获取缓存分析 |
| POST | `/api/diagnosis/error-log/{id}/analyze` | SSE 智能剖析 |
| POST | `/api/diagnosis/error-log/{id}/re-analyze` | 强制重分析 |
| POST | `/api/diagnosis/sn/analyze` | SN 流式分析 |
| POST | `/api/diagnosis/sn/save-history` | 保存历史 |
| PUT | `/api/diagnosis/sn/history/{id}/chat` | 追加聊天 |
| GET | `/api/diagnosis/sn/history` | 历史列表 |
| GET | `/api/diagnosis/sn/history/{id}` | 历史详情 |

### Error logs

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/error-logs/stats` | 统计 |
| GET | `/api/error-logs/trend` | 趋势 |
| GET | `/api/error-logs/stats/yield` | 良率 |

### Analytics

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/analytics/insights` | 看板数据 |

### Sync

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/sync/trigger` | 手动 SIMS 同步 |
| GET | `/api/sync/servers` | 服务器列表 |
| GET | `/api/sync/servers/{sn}/test-details` | 测试明细 |
| GET | `/api/sync/jobs` | 任务列表 |
| GET | `/api/sync/jobs/{id}` | 任务详情 |
| GET/PUT | `/api/sync/auto-config` | 自动同步配置 |
| POST | `/api/sync/trigger-mes` | MES 维修同步 |

### Knowledge base

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/knowledge-base/documents` | 上传 |
| GET | `/api/knowledge-base/documents` | 列表 |
| PUT/DELETE | `/api/knowledge-base/documents/{id}` | 更新/删除 |
| POST | `/api/knowledge-base/documents/{id}/sync-status` | 刷新 RAG 状态 |
| GET | `/api/knowledge-base/ragflow/status` | RAG 连通性 |
| POST | `/api/knowledge-base/search` | 检索测试 |
| GET | `/api/knowledge-base/formats` | 支持格式 |

### Settings

| Method | Path | 说明 |
|--------|------|------|
| GET/PUT | `/api/settings/ai-config` | 全局 AI 配置 |

### Factories

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/factories` | 厂区列表 |

## 响应格式

多数接口返回 `ApiResponse`：

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "message": "optional"
}
```

SSE 端点返回 `text/event-stream`，见 [诊断路由](/routers/diagnosis)。

## 全局异常

`app/main.py` `@app.exception_handler(Exception)` → 500 + `{ success: false, error: str }`。

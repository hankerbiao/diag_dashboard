# API 概览

Base URL: `http://<host>:8000/api`

## 认证

除 OA callback 和 `health` 外，业务 API 需：

```
Authorization: Bearer <access_token>
```

## 响应约定

```typescript
interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string | null
  message?: string | null
}
```

## SSE

诊断剖析端点 `Content-Type: text/event-stream`：

```
event: progress
data: {"stage":"download","detail":"..."}

event: result
data: {...}

event: error
data: {"message":"..."}
```

## 完整端点列表

见 [路由总览](/routers/overview)。

## 交互式文档

| URL | 说明 |
|-----|------|
| `/docs` | Swagger UI |
| `/redoc` | ReDoc |
| `/openapi.json` | OpenAPI 3 schema |

可用 openapi-generator 生成客户端。

## 版本

当前 API version `1.0.0`（`app/main.py`），无 URL versioning。

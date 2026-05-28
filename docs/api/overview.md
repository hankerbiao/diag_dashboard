# API 概览

## 基础信息

- **Base URL**: `http://localhost:8000/api`
- **认证方式**: `Authorization: Bearer <token>` Header
- **响应格式**: JSON 统一信封

## 响应格式

所有 API 返回统一格式：

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "message": null
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 请求是否成功 |
| `data` | any | 成功时返回的数据 |
| `error` | string | 失败时的错误描述 |

## SSE 流式响应

智能诊断端点使用 SSE（Server-Sent Events）实现流式推送：

```
Content-Type: text/event-stream

event: progress
data: {"stage":"download","detail":"正在下载日志..."}

event: progress
data: {"stage":"ragflow","detail":"正在检索知识库..."}

event: token
data: {"text":"诊"}

event: done
data: {"success":true,"data":{...}}
```

| 事件 | 触发时机 | 数据格式 |
|------|---------|---------|
| `progress` | 阶段切换 | `{"stage","detail"}` |
| `token` | LLM 输出 | `{"text"}` |
| `done` | 分析完成 | `{"success","data"}` |
| `error` | 分析失败 | `{"message"}` |

## 认证

除 `/api/auth/login` 和 `/api/auth/register` 外，所有端点需要 Bearer Token。
详见[认证 API](/api/auth)。

## 分页

列表接口统一分页格式：

```json
{
  "success": true,
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "limit": 50
  }
}
```

## ObjectId 处理

MongoDB 的 `_id` 字段在 API 响应中自动转为字符串 `id` 字段。

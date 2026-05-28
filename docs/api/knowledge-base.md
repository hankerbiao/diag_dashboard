# 知识库 API

## POST /api/knowledge-base/documents

上传知识库文档。

**Request:** `multipart/form-data`

| 字段 | 类型 | 说明 |
|------|------|------|
| `file` | file | 上传文件 |
| `title` | string | 文档标题 |
| `description` | string | 文档描述 |
| `tags` | string | 逗号分隔的标签 |

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "xxx",
    "title": "内存故障手册",
    "status": "parsing",
    "format": "pdf",
    "size_bytes": 1024000,
    "tags": ["内存", "故障排查"],
    "uploaded_at": "2024-01-01T00:00:00"
  }
}
```

## GET /api/knowledge-base/documents

获取文档列表。

**Query Parameters:**
| 参数 | 说明 |
|------|------|
| `search` | 标题搜索 |
| `format` | 文件类型过滤（pdf/docx/txt...） |
| `tag` | 标签过滤 |
| `page` | 页码 |
| `limit` | 每页条数 |
| `sync_status` | 是否同步 RAGFlow 状态 |

## DELETE /api/knowledge-base/documents/{doc_id}

删除文档。同时删除 RAGFlow 端文档和本地文件。

## PUT /api/knowledge-base/documents/{doc_id}

更新文档元数据（标题/描述/标签）。

## POST /api/knowledge-base/documents/{doc_id}/sync-status

轮询 RAGFlow 解析状态。

## POST /api/knowledge-base/search

知识库检索测试。

**Request:**
```json
{
  "question": "内存 ECC 错误如何处理"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "references": [
      {
        "chunk_id": "xxx",
        "content": "ECC 错误处理方法...",
        "similarity": 0.95,
        "doc_name": "内存故障手册"
      }
    ]
  }
}
```

## GET /api/knowledge-base/ragflow/status

获取 RAGFlow 连接状态。

## GET /api/knowledge-base/formats

获取支持的文件类型列表。

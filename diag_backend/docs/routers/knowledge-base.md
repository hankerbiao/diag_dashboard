# 知识库路由 (knowledge-base)

**文件：** `app/routers/knowledge_base.py`

Prefix: `/api/knowledge-base`

## POST /documents

`multipart/form-data`：`file`, `title`, `tags`（可选）

1. 存本地 `KNOWLEDGE_BASE_STORAGE_PATH`
2. insert `knowledge_documents`
3. 若 RAGFlow 可用：upload + trigger parsing

## GET /documents

分页列表，字段含 `status`（pending/processing/ready/failed）。

## POST /documents/:id/sync-status

轮询 RAGFlow 解析状态，更新 MongoDB。

## DELETE /documents/:id

删本地文件 + MongoDB + RAGFlow document（若存在）。

## PUT /documents/:id

更新 title/tags。

## POST /search

Body: `{ query, top_k }` — 调试 RAG 检索。

## GET /ragflow/status

返回 RAGFlow 是否配置、dataset/chat 是否就绪。

## GET /formats

允许上传的扩展名列表。

详见 [知识库双写工作流](/workflows/knowledge-base) 与 [RAGFlow 服务](/services/ragflow-service)。

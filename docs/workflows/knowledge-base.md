# 知识库管理

系统支持本地文件存储 + RAGFlow 可选同步的双存储策略。

## 架构

```
Frontend                     Backend                      RAGFlow
  │                            │                            │
  │ 上传文件                    │                            │
  │───────────────────────────▶│                            │
  │                            │── 写入本地文件 ──────────▶│ filesystem
  │                            │── 写入 MongoDB 记录 ─────▶│ knowledge_documents
  │                            │                            │
  │                            │── POST /api/v1/dataset ──▶│ 创建数据集（懒初始化）
  │                            │── POST /api/v1/document ─▶│ 上传文档
  │                            │── POST /api/v1/parse ────▶│ 触发解析
  │                            │                            │
  │                            │◀── 状态轮询 ─────────────│
  │                            │                            │
  │ 搜索/诊断                   │                            │
  │───────────────────────────▶│                            │
  │                            │── POST /api/v1/retrieval ─▶│ 语义检索
  │                            │◀── 参考文档 ─────────────│
```

## RAGFlow 集成

### 懒初始化

系统首次使用 RAGFlow 时会自动创建默认数据集和聊天助手：

```python
# ragflow_service.py
dataset = await ragflow.create_dataset("WeaveEye 知识库")
chat = await ragflow.create_chat("WeaveEye 聊天助手", dataset_id)
```

创建后缓存在内存中，后续请求直接复用。

### 文档状态

| 状态 | 含义 |
|------|------|
| `queued` | 等待解析 |
| `parsing` | 解析中 |
| `parsed` | 解析完成 |
| `failed` | 解析失败 |

前端通过 `sync_status` 参数触发状态轮询。

### 检索流程

诊断分析时调用 `ragflow_service.search_knowledge_base()`：

```
POST /api/v1/retrieval
{
  "question": "fail_details + test_item + fault_type...",
  "top_k": 10
}
```

返回结果按文档名去重，同一文档的多条 chunk 合并后传给 LLM。

## MongoDB 集合

```json
// knowledge_documents
{
  "_id": ObjectId,
  "title": "文档标题",
  "description": "文档描述",
  "format": "pdf",        // 文件类型
  "size_bytes": 1024000,
  "status": "parsed",     // queued/parsing/parsed/failed
  "tags": ["tag1", "tag2"],
  "file_path": "/data/knowledge/xxx.pdf",
  "ragflow_doc_id": "RAGFlow 端文档 ID",
  "uploaded_at": "2024-01-01T00:00:00Z"
}
```

## 前端组件

| 组件 | 功能 |
|------|------|
| `UploadZone` | 拖拽/点击上传，展示文件类型限制 |
| `DocCard` | 文档卡片，显示标题/状态/标签/大小 |
| `DocDetailDrawer` | 右侧抽屉，编辑文档元数据 |
| `KnowledgeBaseTab` | 主页面，文档列表 + 搜索/过滤/排序 |
| `SearchTest` | 检索测试面板，输入问题预览参考结果 |

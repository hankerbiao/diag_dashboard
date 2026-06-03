# RAGFlow 服务

**文件：** `app/services/ragflow_service.py`

函数式模块，封装 RAGFlow HTTP API。

## 配置检查

```python
def _ok() -> bool:
    return bool(url and api_key)
```

未配置时所有公开函数应安全降级。

## 主要 API

| 函数 | RAGFlow 能力 |
|------|--------------|
| `list_datasets` / `create_dataset` | 数据集 |
| `upload_document` / `run_parsing` | 文档上传解析 |
| `list_documents` / `get_document_status` | 状态轮询 |
| `search_knowledge_base` | 向量检索 |
| `create_chat` / `chat_completion` | Chat 助手 |
| `resolve_default_dataset` | 默认 dataset id |
| `map_status` | 状态映射给前端 |

## HTTP 客户端

内部 `httpx.AsyncClient`，短超时 `_client(timeout=T_SHORT)`。

## 诊断集成

`diagnosis.py` 在 `ragflow` 阶段调用 `search_knowledge_base`，top_k 默认 10，结果注入 LLM prompt 并返回 `knowledge_refs`。

## 知识库路由

`knowledge_base.py` 上传后异步触发 parsing，`sync-status` 轮询更新 `knowledge_documents.status`。

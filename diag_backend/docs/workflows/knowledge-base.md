# 知识库双写

## 写入路径

1. **本地** — `data/knowledge_base/{uuid}_{filename}`
2. **MongoDB** — `knowledge_documents` 元数据
3. **RAGFlow**（可选）— dataset document + parsing

## 状态机

| status | 含义 |
|--------|------|
| pending | 已上传待同步 |
| processing | RAG 解析中 |
| ready | 可检索 |
| failed | 解析失败 |

## 诊断时使用

`ragflow_service.search_knowledge_base(query, top_k)` → 注入 LLM + 返回 refs。

## 未配置 RAGFlow

上传仍成功；search 返回空；诊断跳过 ragflow 阶段或仅用知识图谱。

## API

见 [知识库路由](/routers/knowledge-base)。

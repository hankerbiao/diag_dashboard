# 知识图谱服务

**文件：** `app/services/knowledge_graph.py`

## 职责

从 MongoDB 多集合聚合「诊断上下文」：

| 方法 | 数据源 |
|------|--------|
| `get_device_by_sn` | `devices` |
| `search_similar_cases` | `case_library` text/error_code |
| `get_maintenance_by_sn` | `maintenance_records` |
| `get_error_logs_by_device` | `error_logs` |

## 使用场景

- SN 诊断 `_gather_sn_data`
- 非 RAG 的结构化历史参考

## 索引依赖

- `devices.sn` unique
- `case_library` text index on root_cause
- `error_logs (device_id, test_time)`

## 注意

知识图谱与 RAGFlow **互补**：前者结构化 MongoDB 数据，后者非结构化文档向量检索。

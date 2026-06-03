# MongoDB 集合参考

数据库名：`diag_analysis`（可配置）

## users

| 字段 | 说明 |
|------|------|
| email | unique |
| hashed_password | bcrypt |
| created_at | ISO |

## app_settings

每用户设置，`user_id` unique。

## devices

| 字段 | 说明 |
|------|------|
| sn | unique |
| model, customer, ... | 设备信息 |

## error_logs / maintenance_records / case_library

诊断知识图谱数据源，见 [知识图谱](/services/knowledge-graph)。

## sync_remote_servers

| 字段 | 说明 |
|------|------|
| factory_id + server_sn | 复合 unique |
| server_sn | 索引 |
| product_models | 机型 |
| server_state | 状态 |
| synced_at | 同步时间 |

## sync_remote_test_details

| 字段 | 说明 |
|------|------|
| factory_id, server_sn, server_id | 关联 |
| test_time | ISO 字符串 |
| detailed_flow | 工站 |
| server_test_result | 成功/失败 |
| fault_type1/2/3 | 故障分类 |
| decision | 判定 |
| log | SIMS 日志路径 |

## sync_jobs

同步任务状态与 progress 文本。

## auto_sync_configs

自动同步 schedule，含 `__mes__` 特殊项。

## factory_sites

YAML seed 的厂区副本。

## diagnosis_cache

异常剖析结果，**error_log_id unique**。

## diagnosis_sn_history

SN 诊断历史 + chat_messages 数组。

## knowledge_documents

知识库文件元数据 + ragflow_document_id。

## analytics_snapshots

看板预计算 JSON，`computed_at` 索引。

## global_app_config

`_id: ai_config` 全局 AI 配置。

## 关联策略

- 1:1 紧密数据：嵌入文档（少用）
- 1:N 独立查询：`_id` 或业务键引用
- sync 与 devices **未强制 FK**，通过 server_sn 逻辑关联

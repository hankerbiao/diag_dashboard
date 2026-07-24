# MongoDB 集合参考

## 用户认证

### users

| 字段 | 类型 | 说明 | 索引 |
|------|------|------|------|
| `_id` | ObjectId | 主键 | 默认 |
| `itcode` | string | OA 用户唯一标识 | unique, sparse |
| `name` | string | OA 用户显示名 | |
| `email` | string/null | OA 邮箱（可选） | |
| `profile` | object | OA payload 完整资料 | |
| `created_at` | datetime | 创建时间 | |
| `updated_at` | datetime | 资料更新时间 | |
| `last_login_at` | datetime | 最近登录时间 | |

### app_settings

| 字段 | 说明 | 索引 |
|------|------|------|
| `user_id` | 用户 ID（唯一） | unique |
| `ai_model` | LLM 模型名 | |
| `ai_temperature` | 温度参数 | |
| `active_kbs` | 启用知识库列表 | |

### oa_login_assertions

| 字段 | 说明 | 索引 |
|------|------|------|
| `_id` | 已消费 OA payload 的 SHA-256 | 默认唯一 |
| `expires_at` | OA token 过期时间 | TTL |
| `consumed_at` | 回调消费时间 | |

## 业务数据

### sync_remote_servers

| 字段 | 说明 | 索引 |
|------|------|------|
| `factory_id` | 厂区 ID | 复合唯一 `(factory_id, server_sn)` |
| `server_sn` | 设备 SN | 独立索引 |
| `product_models` | 产品型号 | 独立索引 |
| `model` | 设备型号 | |
| `host_ip` | IP 地址 | |
| `server_state` | 测试状态 | |
| `test_items` | 测试项 | |
| `next_item` | 下一步骤 | |
| `position` | 工站位置 | |
| `customer_name` | 客户名 | |
| `alarm` | 告警标志 | |
| `synced_at` | 同步时间戳 | |

### sync_remote_test_details

| 字段 | 说明 | 索引 |
|------|------|------|
| `factory_id` | 厂区 ID | 复合 `(factory_id, server_sn, test_time)` |
| `server_sn` | 设备 SN | |
| `big_flow` | 主流程 | |
| `detailed_flow` | 详细流程 | |
| `decision` | 判定结论（PASS/FAIL） | |
| `server_test_result` | 测试结果详情 | |
| `test_time` | 测试时间 | |
| `fault_type1/2/3` | 故障类型三级分类 | |
| `log_path` | 日志文件路径 | |
| `mes_record` | MES 记录 | |

### sync_jobs

| 字段 | 说明 | 索引 |
|------|------|------|
| `factory_id` | 厂区 ID | 复合 `(factory_id, started_at)` |
| `status` | 状态（running/done/failed） | 独立索引 |
| `started_at` | 开始时间 | |
| `finished_at` | 结束时间 | |
| `error` | 错误信息 | |

## 诊断数据

### diagnosis_cache

| 字段 | 类型 | 说明 |
|------|------|------|
| `error_log_id` | string | 错误日志 ID（唯一索引） |
| `sn` | string | 设备 SN |
| `root_cause` | string | 根本原因 |
| `evidence` | string[] | 关键证据 |
| `analysis` | string | 详细分析 |
| `repair_suggestions` | string[] | 维修建议 |
| `knowledge_refs` | object[] | 知识库引用 |
| `log_content` | string | 日志内容 |
| `created_at` | datetime | 缓存创建时间 |

## 看板数据

### analytics_snapshots

| 字段 | 说明 | 索引 |
|------|------|------|
| `cache_key` | 缓存键 | unique |
| `insights` | 聚合数据对象 | |
| `computed_at` | 计算时间戳 | 独立索引 |

## 知识库

### knowledge_documents

| 字段 | 说明 |
|------|------|
| `title` | 文档标题 |
| `description` | 文档描述 |
| `format` | 文件格式 |
| `size_bytes` | 文件大小 |
| `status` | 解析状态 |
| `tags` | 标签列表 |
| `file_path` | 本地文件路径 |
| `ragflow_doc_id` | RAGFlow 文档 ID |
| `uploaded_at` | 上传时间 |

## 厂区配置

### factory_sites

从 `configs/factories.yaml` seed 的数据。

| 字段 | 说明 | 索引 |
|------|------|------|
| `factory_id` | 厂区 ID（唯一） | unique |
| `name` | 厂区名称 |
| `base_url` | MES API 地址 |
| `log_base_url` | 日志下载地址 |

### auto_sync_configs

| 字段 | 说明 |
|------|------|
| `factory_id` | 厂区 ID |
| `enabled` | 是否启用自动同步 |
| `interval_minutes` | 同步间隔 |
| `hours_back` | 回溯小时数 |

## 关联策略

- **紧耦合 1:1** → 嵌入文档
- **独立查询 1:N** → `_id` 引用
- **自动 ObjectId 转换** → API 响应中 `_id` → `id`（string）

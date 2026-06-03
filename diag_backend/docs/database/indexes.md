# 索引策略

索引在 `app/core/mongodb_indexes.py` 的 `ensure_indexes()` 维护，**启动自动创建**。

## 原则

1. `create_index` 幂等 — 相同 spec 重复调用安全
2. **避免**每次启动 `drop_index`（会导致 QueryPlanKilled）
3. 迁移：仅当旧索引 spec 错误时条件 drop（见 `_ensure_sync_server_sn_index`）

## 分析类索引

`sync_remote_test_details` 上：

- `(test_time DESC)` — 时间范围 match
- `(fault_type1, test_time)` — 故障分类聚合
- `(server_test_result, test_time)` — 良率
- `(detailed_flow, server_test_result)` — 工站失败

## Lookup 索引

`sync_remote_servers.server_sn` — `model_defects` 管道 `$lookup` 外键。

## 唯一约束

| 集合 | 键 |
|------|-----|
| users | email |
| devices | sn |
| sync_remote_servers | (factory_id, server_sn) |
| diagnosis_cache | error_log_id |
| factory_sites | factory_id |

## 手动检查

```javascript
db.sync_remote_servers.getIndexes()
db.sync_remote_test_details.getIndexes()
```

## 添加新索引

1. 编辑 `mongodb_indexes.py`
2. 部署重启
3. 大集合上建索引可能阻塞 — 生产可考虑 `createIndexes` 后台模式（Motor 默认 foreground）

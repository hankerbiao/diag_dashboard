# 索引与 Seed

**文件：** `app/core/mongodb_indexes.py`

启动时由 `connect_mongodb()` 调用，**幂等**。

## ensure_indexes()

为各集合创建索引。关键集合：

### sync_remote_servers

- `idx_sync_servers_sn` — `server_sn`（非 unique）
- `idx_sync_servers_factory_sn` — `(factory_id, server_sn)` unique
- `idx_sync_servers_synced_at`
- `idx_sync_servers_product_models`

**迁移：** `_ensure_sync_server_sn_index()` 仅在旧索引为 **unique** 时才 drop，避免每次启动删索引导致 QueryPlanKilled。

### sync_remote_test_details

- 复合唯一：`(factory_id, server_id, detailed_flow, test_time)`
- 查询：`(factory_id, server_sn, test_time)`
- 分析：`(test_time)`, `(fault_type1, test_time)`, `(server_test_result, test_time)`, `(detailed_flow, server_test_result)`

### 其他

- `users.email` unique
- `diagnosis_cache.error_log_id` unique
- `diagnosis_sn_history` 多索引
- `analytics_snapshots.computed_at`
- 详见 [索引策略](/database/indexes)

## seed_default_data()

1. 从 `factories.yaml` upsert `factory_sites`
2. 每厂区 upsert `auto_sync_configs`（默认 disabled, 60min）
3. upsert `__mes__` MES 全局同步配置
4. `seed_global_ai_config` — 从 `.env` `$setOnInsert` AI 配置

## 历史脚本

`migrations/init_mongodb.py` 为早期手动初始化，**新部署依赖 ensure_indexes**，不必单独跑 migration。

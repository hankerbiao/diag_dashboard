# 厂区 SIMS 同步

## 数据流

```
scripts/sync_data.py
  → queryTestingServers / test details API
  → upsert sync_remote_servers (factory_id + server_sn)
  → upsert sync_remote_test_details
```

## 触发方式

1. **自动** — `SyncSchedulerService` 读 `auto_sync_configs`
2. **手动** — `POST /api/sync/trigger?factory_id=&hours=`
3. **CLI** — `cd scripts && python sync_data.py --factory kunshan --hours 24`

## sync_jobs 文档

```json
{
  "factory_id": "kunshan",
  "sync_type": "sims",
  "status": "running|completed|failed",
  "started_at": "...",
  "progress": "stdout tail",
  "error": "stderr tail"
}
```

## 去重键

- servers: `(factory_id, server_sn)`
- details: `(factory_id, server_id, detailed_flow, test_time)`

## MES 维修同步

`POST /api/sync/trigger-mes` → `scripts/sync_mes.py` → `maintenance_records` + RAGFlow

配置项：`auto_sync_configs` 中 `factory_id: __mes__`

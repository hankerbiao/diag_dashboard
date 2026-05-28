# 厂区数据同步

## 架构

```
┌──────────────────────────────────────────────────────────┐
│             独立同步脚本 (scripts/sync_data.py)            │
│  读取 factories.yaml → 遍历厂区 → 调用 MES API → 写入    │
│  可 cron 定时触发或手动执行                                │
└──────────────────────────┬───────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
         MES API (厂区)            MongoDB
     queryTestingServers        sync_remote_servers
     queryTestList              sync_remote_test_details
                                sync_jobs
                           ▲
                           │
┌──────────────────────────┴───────────────────────────────┐
│         Backend SyncService (只读)                        │
│  GET /api/sync/servers                                   │
│  GET /api/sync/servers/{sn}/test-details                 │
└──────────────────────────────────────────────────────────┘
```

**数据写入路径**: 独立脚本 `scripts/sync_data.py`（唯一写入者）  
**数据读取路径**: 后端 `SyncService` 提供只读查询接口  
**前端查询**: `syncApi.getServers()` / `getTestDetails()`

## 数据源

每个厂区对应一个 MES API，由 `configs/factories.yaml` 配置。同步脚本遍历所有启用的厂区进行拉取。

## 同步策略

### 全量分页拉取

每次同步执行全量拉取（不带时间水印），通过 upsert 去重：

```python
# sync_remote_servers 去重键: (factory_id, server_sn)
# sync_remote_test_details 去重键: (server_id, detailed_flow, test_time)
```

### 并发控制

- `asyncio.Lock` — 防止同一脚本实例并发执行
- `asyncio.Semaphore(5)` — 控制 MES API 并发请求数
- 每 SN 重试 3 次，指数退避

### 同步方式

| 参数 | 说明 |
|------|------|
| `--hours 24` | 仅最近 24 小时（默认） |
| `--hours 0` | 全量同步 |
| `--factory kunshan` | 仅同步指定厂区 |
| `--dry-run` | 试运行，不写入数据库 |

## 集合

| 集合 | 用途 | 核心索引 |
|------|------|---------|
| `sync_remote_servers` | 服务器列表 | (factory_id, server_sn) 复合唯一 |
| `sync_remote_test_details` | 测试明细 | (factory_id, server_sn, test_time) |
| `sync_jobs` | 同步日志 | status, started_at |

## 前端集成

```
ErrorLogsTab
  └→ 搜索 SN/型号 → syncApi.getServers()
       └→ 服务器列表 → 点击选择 SN
            └→ ServerDetailModal → getTestDetails()
                 └→ ErrorTable（失败记录列表）
                      └→ AnalysisModal（AI 诊断）
```

详见设计文档: `docs/design/data-sync-module.md`

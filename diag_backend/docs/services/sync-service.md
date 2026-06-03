# 同步服务

**文件：** `app/services/sync_service.py`

## 职责

查询类同步 API 的数据访问（servers、test-details、jobs），不含 subprocess。

## 主要方法

- 分页查询 `sync_remote_servers`（filter/sort/skip/limit）
- 查询 `sync_remote_test_details` by server_sn
- 读取 `sync_jobs` 状态

## 与 SyncScheduler 边界

| SyncService | SyncSchedulerService |
|-------------|---------------------|
| 读 MongoDB | 写 sync_jobs + 跑脚本 |
| sync router GET | trigger + 自动调度 |

## 索引

依赖 `idx_sync_servers_factory_sn`、`idx_sync_details_factory_sn_time` 等。

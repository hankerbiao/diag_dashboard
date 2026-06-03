# 同步路由 (sync)

**文件：** `app/routers/sync.py`

Prefix: `/api/sync`

## POST /trigger

手动触发某厂区 SIMS 同步：

- Query: `factory_id`, `hours`（cutoff）
- 委托 `SyncSchedulerService` 或 `SyncService`
- 防并发：同厂区 running job 跳过

## GET /servers

分页查询 `sync_remote_servers`：

- 过滤：`factory_id`, `sn`, `product_models`（regex）
- 排序：最近测试时间

## GET /servers/{server_sn}/test-details

查 `sync_remote_test_details`，供异常看板测试详情 Modal。

## Jobs

- `GET /jobs` — 列表
- `GET /jobs/{job_id}` — 状态、progress、output、error

## Auto config

- `GET /auto-config` — 读 `auto_sync_configs`
- `PUT /auto-config` — 更新 enabled、interval_minutes、cutoff_hours

## POST /trigger-mes

触发 `scripts/sync_mes.py` 子进程，同步维修记录 + 可选 RAGFlow 上传。

详见 [厂区 SIMS 同步](/workflows/factory-sync) 与 [同步调度器](/services/sync-scheduler)。

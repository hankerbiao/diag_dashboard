# 同步调度器

**文件：** `app/services/sync_scheduler_service.py`

## 职责

- 每 **60 秒** 轮询 `auto_sync_configs`
- 到期则 subprocess 执行 `scripts/sync_data.py` 或 `sync_mes.py`
- 更新 `sync_jobs` progress

## 配置键

| factory_id | 含义 |
|------------|------|
| `kunshan`, ... | 各厂区 SIMS 同步 |
| `__mes__` | 全局 MES 维修同步（`MES_CONFIG_KEY`） |

字段：`enabled`, `interval_minutes`, `cutoff_hours`, `last_run_at`

## execute_sync_script

```python
asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
```

- 每 2s flush stdout 到 `sync_jobs.progress`
- 完成写 `status` completed/failed + stderr tail

## 并发控制

`_running_jobs` dict 防止同厂区重复触发；返回 `{ status: skipped }`。

## 脚本路径

```python
_SCRIPTS_DIR = repo_root/scripts
```

## 手动触发

`POST /api/sync/trigger` 与调度器共用 `_run_sims_sync` 逻辑。

详见 [厂区 SIMS 同步](/workflows/factory-sync)。

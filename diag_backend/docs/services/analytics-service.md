# 分析看板服务

**文件：** `app/services/analytics_service.py`

## 职责

- 预计算看板 6 类聚合数据
- 写入 `analytics_snapshots` 缓存
- 后台每小时 `refresh_all()`

## 缓存键

```python
_key(trend, days, fac=factory_id, sn=..., pm=...)
# 例: insights:day:30:fac:kunshan
```

有 `search_sn` 或 `search_product_models` 时 **不读快照**，实时 `_compute`。

## _compute 并行聚合

`asyncio.gather` 六路：

1. fault_type1 Top10
2. fault_type2 Top10
3. yield_trend（按 day/week/month）
4. detailed_flow 工站失败
5. decision 分布
6. model_defects（`$lookup sync_remote_servers`）

## QueryPlanKilled (175)

`_run` 对 MongoDB error code 175 重试 3 次（索引 rebuild 窗口）。

根因修复见 `mongodb_indexes._ensure_sync_server_sn_index`。

## 启动行为

`start()` → `_loop()` 立即 `refresh_all()`，然后每 3600s 重复。

## Semaphore

`refresh_all` 用 `Semaphore(5)` 限制并发 aggregation，避免打满 MongoDB。

详见 [看板预计算工作流](/workflows/analytics-snapshot)。

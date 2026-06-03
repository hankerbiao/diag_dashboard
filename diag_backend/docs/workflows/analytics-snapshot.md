# 看板快照预计算

## 为什么预计算

`sync_remote_test_details` 数据量大，实时 aggregation 压 MongoDB；默认读 **快照**。

## 快照集合

`analytics_snapshots`:

```json
{
  "_id": "insights:day:30:fac:kunshan",
  "data": { "fault_categories": [...], ... },
  "computed_at": ISODate
}
```

## 刷新策略

- 启动立即 `refresh_all()`
- 之后每 **3600s**
- 全厂区 × 三种 trend (day/week/month) × 全局

## 实时例外

带 `search_sn` / `search_product_models` 的 insights 请求 bypass 快照。

## model_defects 管道

含 `$lookup` 到 `sync_remote_servers`，依赖 `idx_sync_servers_sn`。

## 故障

见 [故障排查](/operations/troubleshooting) QueryPlanKilled 条目。

# 数据看板

## 预计算快照策略

看板数据通过 `AnalyticsService` 每小时预计算，避免实时聚合压力。

### 调度器

```python
# analytics_service.py
async def _scheduler_loop(self):
    await self._compute_and_cache()   # 启动时立即计算
    while True:
        await asyncio.sleep(3600)     # 之后每小时执行
        await self._compute_and_cache()
```

### 缓存键

```python
# 模式: insights:{trend}:{days}[:fac:{factory_id}]
"_cache_key(trend='day', days=30, factory_id='kunshan')"
# → "insights:day:30:fac:kunshan"
```

预计算覆盖 3 种趋势粒度（day/week/month）× 每个厂区 + 1 个总览 = ~18 个快照。

### 实时 vs 缓存

| 请求条件 | 行为 |
|---------|------|
| 无过滤器（仅 factory/days/trend） | 直接读取 MongoDB 快照 |
| 带 search_sn/search_product_models | 实时聚合（`asyncio.gather` 并行 6 个管道） |

## 6 个图表

| 图表 | 聚合管道 | 前端组件 |
|------|---------|---------|
| 故障类别分布 | `fault_type1` 分组计数 + TOP10 | `BatchFaultPieChart` |
| 故障子类别分布 | `fault_type2` 分组计数 + TOP10 | `BatchSubfaultBarChart` |
| 日良率趋势 | 按日期分组 + 成功/失败计数 + 良率% | `BatchYieldTrendChart` |
| 工站失败数 | `detailed_flow`（失败）分组 + TOP10 | `BatchStationBarChart` |
| 判定结果分布 | `decision` 分组计数 | `BatchDecisionPieChart` |
| 机型不良率 | `$lookup servers` + 机型分组 | `BatchModelComparisonChart` |

管道使用 `asyncio.gather` 并行执行：

```python
results = await asyncio.gather(
    self._pipeline_fault_categories(pipeline),
    self._pipeline_fault_subcategories(pipeline),
    self._pipeline_yield_trend(pipeline),
    self._pipeline_station_failures(pipeline),
    self._pipeline_decision_distribution(pipeline),
    self._pipeline_model_defects(pipeline),
)
```

## 前端集成

- **默认视图**：`ErrorLogsTab` 未搜索时显示 2×3 图表网格
- **搜索后**：图表区域替换为服务器列表
- **趋势切换**：日/周/月 粒度控制
- **三态**：加载骨架屏 / 空状态 / 数据渲染

## 关键代码文件

| 文件 | 作用 |
|------|------|
| `app/services/analytics_service.py` | 预计算调度、6 个聚合管道、快照读写 |
| `app/routers/analytics.py` | `/api/analytics/insights` 端点 |
| `src/api/fastapi.ts` | `analyticsApi.getInsights()` |
| `src/components/error-logs/charts/` | 6 个图表组件 |

详见设计文档: `docs/analytics-dashboard-design.md`

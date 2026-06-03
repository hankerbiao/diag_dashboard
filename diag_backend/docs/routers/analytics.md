# 分析路由 (analytics)

**文件：** `app/routers/analytics.py`

## GET /api/analytics/insights

**Query 参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `factory_id` | string | — | 厂区过滤 |
| `days` | int | 30 | 统计窗口 |
| `trend` | string | day | day/week/month 良率粒度 |
| `search_sn` | string | — | SN 模糊搜索（实时计算） |
| `search_product_models` | string | — | 机型搜索（实时计算） |

**响应 data 字段：**

| 键 | 内容 |
|----|------|
| `fault_categories` | fault_type1 Top N |
| `fault_subcategories` | fault_type2 Top N |
| `yield_trend` | 良率时间序列 |
| `station_failures` | 工站失败 Top N |
| `decision_distribution` | 判定分布 |
| `model_defects` | 机型缺陷 Top 10 |

实现：`get_analytics_service().get_insights(...)`

详见 [看板预计算](/workflows/analytics-snapshot) 与 [AnalyticsService](/services/analytics-service)。

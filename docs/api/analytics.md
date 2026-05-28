# 数据分析 API

## GET /api/analytics/insights

获取看板聚合数据。

**Query Parameters:**
| 参数 | 类型 | 说明 |
|------|------|------|
| `factory_id` | string | 厂区 ID（可选，不传则查全部） |
| `search_sn` | string | 按 SN 过滤（触发实时计算） |
| `search_product_models` | string | 按型号过滤（触发实时计算） |
| `days` | number | 时间范围天数（默认 30） |
| `trend` | string | 趋势粒度：day/week/month |

**Response:**
```json
{
  "success": true,
  "data": {
    "fault_categories": [
      {"name": "内存故障", "count": 45}
    ],
    "fault_subcategories": [...],
    "yield_trend": [
      {"date": "2024-01-01", "total": 100, "passed": 95, "failed": 5, "yield": 95.0}
    ],
    "station_failures": [
      {"station": "内存测试站", "count": 30}
    ],
    "decision_distribution": [
      {"decision": "PASS", "count": 950}
    ],
    "model_defects": [
      {"model": "R750", "total": 100, "failed": 8, "yield": 92.0}
    ]
  }
}
```

**缓存策略:**
- `search_sn` 或 `search_product_models` 为空 → 读取预计算快照
- 带过滤条件 → 实时 MongoDB 聚合

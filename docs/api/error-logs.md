# 错误日志 API

## GET /api/error-logs/stats

获取错误日志统计（趋势 + 良率 + 类型 + 线体统计）。

**Query Parameters:**
| 参数 | 说明 |
|------|------|
| `factory` | 厂区 ID |
| `time_range` | 时间范围（7d/30d） |

**Response:**
```json
{
  "success": true,
  "data": {
    "trend": [{"time": "2024-01-01", "issues": 5}],
    "yield_trend": [{"date": "2024-01-01", "yield_": 95.5}],
    "by_type": [{"name": "内存故障", "count": 20}],
    "by_line": [{"line": "产线A", "issues": 15}]
  }
}
```

> 当前为 mock 数据，后续接入真实数据源。

## GET /api/error-logs/trend

错误趋势时间序列。

## GET /api/error-logs/stats/yield

良率趋势。

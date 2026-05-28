# 数据同步 API

> 所有同步 API 为只读查询，数据由独立脚本写入。

## GET /api/sync/servers

获取服务器列表（支持搜索和分页）。

**Query Parameters:**
| 参数 | 类型 | 说明 |
|------|------|------|
| `factory_id` | string | 厂区过滤 |
| `search_sn` | string | SN 模糊搜索 |
| `search_product_models` | string | 型号搜索 |
| `page` | number | 页码（默认 1） |
| `limit` | number | 每页条数（默认 50） |

**Response:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "xxx",
        "server_sn": "SN20240101",
        "model": "R750",
        "product_models": "PowerEdge",
        "host_ip": "10.0.0.1",
        "server_state": "Testing",
        "test_items": "内存测试,CPU测试",
        "position": "A-01",
        "synced_at": "2024-01-01T00:00:00"
      }
    ],
    "total": 100,
    "page": 1,
    "limit": 50
  }
}
```

## GET /api/sync/servers/{server_sn}/test-details

获取指定服务器的测试明细。

**Query Parameters:**
| 参数 | 说明 |
|------|------|
| `factory_id` | 厂区 ID |
| `page` | 页码 |
| `limit` | 每页条数 |

**Response:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "xxx",
        "server_sn": "SN20240101",
        "big_flow": "整机测试",
        "detailed_flow": "内存压力测试",
        "decision": "FAIL",
        "server_test_result": "ECC 错误",
        "test_time": "2024-01-01 10:00:00",
        "log_path": "/logs/2024/01/01/test.log",
        "mes_record": ""
      }
    ],
    "total": 50,
    "page": 1,
    "limit": 50
  }
}
```

## GET /api/sync/jobs

同步任务历史记录。

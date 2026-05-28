# 厂区管理 API

## GET /api/factories

获取厂区列表。

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "factory_id": "kunshan",
      "name": "昆山厂",
      "base_url": "http://10.17.154.252:8099/",
      "log_base_url": "http://10.17.154.246:8080/"
    }
  ]
}
```

数据来源：`configs/factories.yaml`，由 `factory_config.py` 读取。

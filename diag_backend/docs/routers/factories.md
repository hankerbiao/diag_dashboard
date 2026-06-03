# 厂区路由 (factories)

**文件：** `app/routers/factories.py`

## GET /api/factories

**无需 MongoDB**，直接 `load_factories_from_yaml()`。

响应示例：

```json
{
  "success": true,
  "data": [
    {
      "factory_id": "kunshan",
      "name": "昆山厂区",
      "base_url": "http://10.8.102.88",
      "log_base_url": "http://10.8.102.89/log"
    }
  ]
}
```

前端用于 Header 厂区选择与诊断/异常看板上下文。

修改厂区请编辑 `configs/factories.yaml` 并重启（或依赖 seed upsert `factory_sites`）。

详见 [厂区配置](/core/factory-config)。

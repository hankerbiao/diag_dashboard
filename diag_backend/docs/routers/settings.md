# 设置路由 (settings)

**文件：** `app/routers/settings.py`

Prefix: `/api/settings`

## GET /ai-config

从 `global_app_config` 读取 `_id: "ai_config"`：

```json
{
  "api_key": "***",
  "base_url": "https://...",
  "model": "gpt-4-turbo",
  "temperature": 0.7,
  "provider": "openai"
}
```

响应可能脱敏 api_key。

## PUT /ai-config

更新 AI 配置，写入 MongoDB，`updated_at` / `updated_by`。

前端 Settings 页保存后即时生效于后续 LLM 调用。

Seed：首次部署 `seed_global_ai_config` 从 `.env` `$setOnInsert`。

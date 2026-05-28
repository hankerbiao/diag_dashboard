# 设置 API

## GET /api/settings

获取系统设置。

**Response:**
```json
{
  "success": true,
  "data": {
    "ai_api_url": "https://api.openai.com/v1",
    "ai_model": "gpt-4",
    "ai_temperature": 0.3,
    "active_kbs": ["knowledge_base"]
  }
}
```

## PUT /api/settings

更新系统设置。

**Request:**
```json
{
  "ai_model": "gemini-2.5-flash",
  "ai_temperature": 0.5
}
```

**Response:** 返回更新后的完整设置对象。

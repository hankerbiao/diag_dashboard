# 认证 API

## POST /api/auth/register

注册新用户。

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
}
```

## POST /api/auth/login

登录获取 JWT Token。

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "remember": false
}
```

**参数说明：**
- `remember: false` — Token 60 分钟过期
- `remember: true` — Token 1 天过期

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
}
```

## GET /api/auth/me

获取当前登录用户信息（需要 Bearer Token）。

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "xxx",
    "email": "user@example.com",
    "created_at": "2024-01-01T00:00:00"
  }
}
```

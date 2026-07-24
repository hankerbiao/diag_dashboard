# 认证 API

WeaveEye 仅支持 OA 单点登录。Springboard 登录成功后把 `status`、`payload`、`next`
附加到前端地址，前端再用回调接口换取应用 Bearer JWT。

## POST /api/auth/oa/callback

```json
{
  "status": "success",
  "payload": "<OA HS256 JWT>",
  "next": "https://weaveeye.example.com/"
}
```

后端使用 `OA_JWT_SECRET` 验证 payload 的 HS256 签名和 `exp`，按 `itcode`
更新用户资料，并返回应用 JWT：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "itcode": "zhangsan",
    "name": "张三",
    "email": "zhangsan@example.com",
    "profile": {}
  }
}
```

## GET /api/auth/me

请求头：`Authorization: Bearer <access_token>`。

返回当前 OA 用户的 `id`、`itcode`、`name`、可选 `email` 和完整 `profile`。

## 已删除接口

- `POST /api/auth/login`
- `POST /api/auth/register`

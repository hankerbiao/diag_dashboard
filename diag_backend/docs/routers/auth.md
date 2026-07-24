# Auth Router

## POST /oa/callback

Body: `{ status, payload, next? }`。

- 要求 `status == "success"`
- 使用 `OA_JWT_SECRET` 验证 HS256 payload 和 `exp`
- 要求 payload 包含 `itcode`
- 按 `itcode` 更新 OA profile
- 返回 `{ access_token, token_type, user }`

## GET /me

需要应用 Bearer JWT，返回当前 OA 用户的 `id`、`itcode`、`name`、可选 `email`
和完整 `profile`。

`/register` 和 `/login` 已删除。

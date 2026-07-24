# OA 与应用 JWT

## OA payload

`POST /api/auth/oa/callback` 使用 `OA_JWT_SECRET` 和 HS256 验证 Springboard
payload。Token 必须有效且包含 `exp`、`itcode`；姓名依次读取 `姓名`、`name`、
`displayName`，最后回退到 `itcode`。

用户按 `itcode` upsert 到 `users`，完整 OA 数据保存在 `profile`。本地账号密码登录
和注册已删除。

OA payload 的 SHA-256 会原子写入 `oa_login_assertions`；重复 payload 被拒绝，记录由
`expires_at` TTL 索引自动清理。

## 应用 Token

回调成功后，`create_access_token` 使用 `JWT_SECRET_KEY` 签发 Bearer JWT，包含：

- `sub`: MongoDB 用户 ID
- `itcode`、`name`、可选 `email`
- `exp`: 由 `ACCESS_TOKEN_EXPIRE_MINUTES` 控制

业务接口继续通过 `Depends(get_current_user)` 验证
`Authorization: Bearer <token>`。

| 端点 | 是否需要应用 Token |
|------|--------------------|
| `POST /api/auth/oa/callback` | 否 |
| `GET /api/auth/me` | 是 |
| 其他业务 API | 是 |

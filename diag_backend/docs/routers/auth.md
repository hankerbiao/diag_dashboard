# 认证路由 (auth)

**文件：** `app/routers/auth.py`

## POST /register

Body: `{ email, password }`

- 检查 email 未占用
- bcrypt 哈希密码
- insert `users`
- 返回 JWT + `UserResponse`

## POST /login

- 验证 email/password
- 签发 JWT
- 可选 remember-me 延长过期（若实现）

## GET /me

需 Bearer token，返回当前用户 `{ id, email, created_at }`。

## 模型

`app/models/auth.py` — `RegisterRequest`, `LoginRequest`, `AuthResponse`, `UserResponse`

## 错误码

- 400 — 邮箱已存在、参数无效
- 401 — 登录失败、token 无效

详见 [JWT 认证工作流](/workflows/authentication)。

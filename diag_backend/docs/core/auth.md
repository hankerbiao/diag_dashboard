# 认证模块 (auth)

**文件：** `app/core/auth.py`

## 密码

- `passlib` bcrypt 哈希
- `bcrypt==4.0.1`  pinned（与 passlib 兼容）

## JWT

- 库：`python-jose`
- 算法：`HS256`（`JWT_ALGORITHM`）
- Payload：`sub` = 用户 email，`exp` 过期时间

## 核心函数

| 函数 | 用途 |
|------|------|
| `hash_password(password)` | 注册时 |
| `verify_password(plain, hashed)` | 登录时 |
| `create_access_token(data, expires_delta?)` | 签发 token |
| `get_current_user(credentials)` | FastAPI Depends，Bearer 解码 |

## get_current_user 流程

1. `HTTPBearer` 提取 token
2. `jwt.decode` + `JWT_SECRET_KEY`
3. 取 `sub` email
4. `users.find_one({"email": email})`
5. 不存在 → 401

## 路由

| 方法 | 路径 | 认证 |
|------|------|------|
| POST | `/api/auth/register` | 否 |
| POST | `/api/auth/login` | 否 |
| GET | `/api/auth/me` | 是 |

## 安全建议

- 生产使用长随机 `JWT_SECRET_KEY`
- 考虑 refresh token（当前未实现）
- CORS 生产应限制 `allow_origins`（当前 `*`）

详见 [JWT 认证工作流](/workflows/authentication)。

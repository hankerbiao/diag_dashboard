# OA 认证流程

系统只接受 OA 单点登录，业务 API 继续使用应用签发的 Bearer JWT。

## 登录流程

1. 未登录用户进入前端，浏览器跳转到
   `http://tl.cooacloud.com/springboard_v3/login_proxy/diagweaveeye?next=<前端地址>`。
2. Springboard 登录成功后把 `status`、`payload`、`next` 附加到前端 URL。
3. 前端生成并保存一次性 state；回调时检查 `status=success`、payload 存在，且
   `next` 同源并携带匹配的 state，然后调用
   `POST /api/auth/oa/callback`。
4. 后端使用 `OA_JWT_SECRET` 校验 OA JWT 的 HS256 签名和有效期，要求包含
   `itcode` 和 `exp`。
5. 后端原子记录 assertion 哈希；已使用过的 payload 会被拒绝，记录随 `exp` 自动过期。
6. 后端按 `itcode` upsert `users`，保存完整 OA profile，并签发应用 JWT。
7. 前端把应用 JWT 保存到 `localStorage`，清理 URL 中的 OA 参数；后续请求通过
   `Authorization: Bearer <token>` 发送。

## 会话恢复与退出

- 页面刷新时通过 `GET /api/auth/me` 恢复用户。
- token 无效时清除本地状态并重新进入 OA 登录流程。
- 主动退出只清除应用 token，并暂停自动跳转；用户可点击“使用 OA 登录”重新进入。
- 历史本地用户首次 OA 登录时，可通过 OA 已验证邮箱绑定原 MongoDB 用户 ID。
- 应用 JWT 有效期由 `ACCESS_TOKEN_EXPIRE_MINUTES` 控制。

## 配置

| 变量 | 说明 |
|------|------|
| `OA_JWT_SECRET` | Springboard 共享的 OA payload 验签密钥，必须配置 |
| `JWT_SECRET_KEY` | WeaveEye 应用 Bearer JWT 签名密钥，至少 32 字符且不可用示例值 |
| `VITE_OA_LOGIN_URL` | 前端 OA 登录地址，可选覆盖 |

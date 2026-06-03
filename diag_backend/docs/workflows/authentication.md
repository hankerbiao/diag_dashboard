# JWT 认证工作流

```mermaid
sequenceDiagram
  participant C as Client
  participant A as /api/auth
  participant U as users collection

  C->>A: POST /register {email, password}
  A->>U: find email
  A->>U: insert hashed password
  A-->>C: { access_token, user }

  C->>A: POST /login
  A->>U: verify
  A-->>C: JWT

  C->>A: GET /me Authorization Bearer
  A->>A: jwt.decode
  A->>U: find by email
  A-->>C: UserResponse
```

## Token 存储（前端）

`localStorage` + `AuthContext`；后端无 session 表，纯 stateless JWT。

## 受保护路由

```python
@router.get("/...")
async def handler(user=Depends(get_current_user)):
    ...
```

## 安全清单

- [ ] 生产更换 JWT_SECRET_KEY
- [ ] HTTPS 传输
- [ ] 限制 CORS
- [ ] 密码强度（当前未强制，可扩展）

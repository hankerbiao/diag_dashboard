# 认证流程

系统使用自建 JWT 认证，不依赖外部认证服务。

## 技术选型

- **密码哈希**: `passlib.context.CryptContext` + bcrypt
- **JWT 签发/验证**: `python-jose`，HS256 算法
- **令牌传输**: `Authorization: Bearer <token>` Header
- **前端存储**: `localStorage`

## 认证流程

```
1. 用户注册 → POST /api/auth/register
   └→ 密码 bcrypt 哈希 → 存入 MongoDB users 集合

2. 用户登录 → POST /api/auth/login
   └→ 验证密码 → 签发 JWT (access_token)
   └→ 普通登录: 60 分钟过期
   └→ 勾选"记住我": 1 天过期

3. 前端存储 → localStorage.setItem("access_token")
   └→ 所有后续请求通过 fetchApi() 自动携带 Bearer Token

4. 后端验证 → Depends(get_current_user)
   └→ HTTPBearer 提取 Token → decode → 返回 user 对象
```

## 前端认证架构

```
App.tsx
  └→ ThemeProvider
       └→ AuthProvider              ← 初始化时验证 Token
            ├→ 有效: setUser() → 显示主界面
            └→ 无效: 清除 Token → 显示 LoginPage
                 └→ AuthGuard       ← 保护所有需要认证的路由

API 调用链:
  Component → fetchApi(endpoint)
              └→ getAccessToken() → Authorization Header
```

## 核心组件

| 文件 | 作用 |
|------|------|
| `app/core/auth.py` | JWT 创建/验证，密码哈希，`get_current_user` 依赖注入 |
| `app/routers/auth.py` | `/register`、`/login`、`/me` 三个端点 |
| `src/api/auth.ts` | 前端认证 API（login/register/token 管理） |
| `src/contexts/AuthContext.tsx` | 认证状态管理（user/loading/signIn/signOut） |
| `src/components/auth/AuthGuard.tsx` | 路由守卫，未认证时重定向到 LoginPage |

## 令牌格式

```json
{
  "sub": "user_id",
  "exp": 1700000000,
  "iat": 1699996400
}
```

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

WeaveEye 前端 — React 19 + TypeScript + Vite + Tailwind CSS 4。后端为 FastAPI + MongoDB，认证为自建 JWT。

## Development Commands

```bash
npm install              # 安装依赖
npm run dev              # 开发服务器 (端口 3000, host 0.0.0.0)
npm run lint             # TypeScript 类型检查 (tsc --noEmit)
npm run build            # 生产构建 (vite build)
```

## Environment

```bash
# .env.local
VITE_API_BASE_URL=http://localhost:8000
```

## Architecture

```
src/
├── api/
│   ├── auth.ts          # JWT 认证 (POST /api/auth/*), token 存 localStorage
│   ├── fastapi.ts       # FastAPI 通用客户端 (fetchApi<T>), Bearer token 透传
│   └── index.ts
├── contexts/
│   ├── AuthContext.tsx   # user/loading/signIn/signUp/signOut, 初始化验证 token
│   └── ThemeContext.tsx
├── components/
│   ├── auth/            # AuthGuard, LoginPage
│   ├── layout/          # Sidebar, Header
│   ├── diagnosis/       # 单机诊断模块
│   ├── dashboard/       # 数据看板
│   ├── error-logs/      # 异常看板
│   ├── settings/        # 设置页
│   └── common/          # 通用组件
├── types/index.ts       # 应用级类型 (camelCase)
└── App.tsx              # ThemeProvider → AuthProvider → AuthGuard → AppContent
```

### 认证流程

```
AuthProvider 初始化 → auth.getCurrentUser()
  └── GET /api/auth/me (Bearer token)
        ├── 有效 → setUser()
        └── 无效 → 清除 token, 显示 LoginPage

登录: auth.signIn() → POST /api/auth/login → 存 token → setUser()
登出: auth.signOut() → 清除 localStorage token → setUser(null)

所有 API 调用: fetchApi() → getAccessToken() → Authorization: Bearer <token>
```

### API 客户端模式

`fastapi.ts` 中 `fetchApi<T>(endpoint, options)` 是统一的 HTTP 客户端：
- 自动从 localStorage 获取 JWT token
- 统一 `ApiResponse<T>` 响应格式：`{ success, data?, error?, message? }`
- 三个 API 模块：`diagnosisApi`, `settingsApi`, `syncApi`

### 类型命名约定

- `src/api/*.ts` 中的接口使用 `snake_case`（匹配 API JSON 响应）
- `src/types/index.ts` 中使用 `camelCase`（应用内部使用）
- 组件中需要时手动映射

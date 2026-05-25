# Plan: Supabase → MongoDB 数据库重构方案

## 需求重述

将 `diag_backend` 和 `diag_frontend` 的数据库层从 Supabase (PostgreSQL) 全面迁移到 MongoDB，包括：
- 数据库 CRUD 操作
- 身份认证（JWT 签发与验证）
- 前端 API 调用

---

## 现状分析

### 当前 Supabase 使用范围

| 层级 | 用途 | 涉及文件数 |
|------|------|-----------|
| 后端 - Auth | `supabase.auth.get_user(token)` 验证 JWT | 1 (`security.py`) |
| 后端 - DB (同步 SDK) | `knowledge_graph.py`, `settings.py` | 3 |
| 后端 - DB (异步 REST) | `sync_service.py` 自定义 `SupabaseAsyncClient` | 1 |
| 后端 - 配置 | `config.py` 3 个环境变量 + `supabase.py` 客户端工厂 | 2 |
| 前端 - Auth | `signIn/Up/Out` + `onAuthStateChange` + session 管理 | 2 (`AuthContext.tsx`, `supabase.ts`) |
| 前端 - DB | `fetchErrorLogs()` (未使用) | 1 (`supabase.ts`) |
| 前端 - Token | `getAccessToken()` → FastAPI Bearer 头 | 2 (`supabase.ts`, `fastapi.ts`) |

### 涉及的 9 张表及关系

| 表名 | 操作类型 | 关联关系 |
|------|---------|---------|
| `app_settings` | SELECT, INSERT, UPDATE | 无 |
| `devices` | SELECT | → `factories` (N:1) |
| `error_logs` | SELECT | → `devices` (N:1) |
| `factories` | SELECT (via JOIN) | 被 `devices` 引用 |
| `maintenance_records` | SELECT | → `devices` (N:1) |
| `case_library` | SELECT + ilike | 无 |
| `sync_jobs` | SELECT, INSERT, UPDATE | 无 |
| `sync_remote_servers` | SELECT, UPSERT | → `sync_remote_test_details` (1:N) |
| `sync_remote_test_details` | SELECT, UPSERT | 被 `sync_remote_servers` 引用 |

### 未使用的 Supabase 功能
- Realtime (WebSocket 订阅)
- Storage (文件存储)
- Edge Functions
- RLS (行级安全)

---

## 目标架构

```
┌─────────────────────────────────────────────────┐
│                   Frontend (React)                │
│  AuthContext → POST /api/auth/login|register     │
│  fastapi.ts  → Authorization: Bearer <jwt>       │
│              → GET/POST /api/*                    │
└────────────────────────┬────────────────────────┘
                         │ HTTP
┌────────────────────────▼────────────────────────┐
│              Backend (FastAPI + Motor)            │
│                                                   │
│  app/core/mongodb.py     ← MongoDB 连接管理       │
│  app/core/security.py    ← 本地 JWT 签发/验证     │
│  app/routers/auth.py     ← 新增: 登录/注册路由    │
│  app/services/*.py       ← motor 异步查询         │
│  app/models/*.py         ← Pydantic + ObjectId    │
└────────────────────────┬────────────────────────┘
                         │
┌────────────────────────▼────────────────────────┐
│               MongoDB (Atlas / 自托管)            │
│  Collections:                                     │
│    users, app_settings, devices, factories,       │
│    error_logs, maintenance_records, case_library, │
│    sync_jobs, sync_remote_servers,                │
│    sync_remote_test_details                       │
└─────────────────────────────────────────────────┘
```

---

## 实施阶段

### Phase 1: 基础设施准备 (约 2 小时)

**1.1 添加 Python 依赖**
- 添加 `motor>=3.6.0` (MongoDB 异步驱动)
- 添加 `pymongo>=4.9.0` (motor 依赖)
- 添加 `passlib[bcrypt]>=1.7.4` (密码哈希)
- 添加 `python-jose[cryptography]>=3.3.0` (JWT 签发/验证，已存在)
- 移除 `supabase>=2.3.0`

**1.2 环境变量更新**
- 新增: `MONGODB_URI=mongodb://localhost:27017` 或 Atlas 连接串
- 新增: `MONGODB_DB_NAME=diag_analysis`
- 新增: `JWT_SECRET_KEY=<生成强密钥>`
- 新增: `JWT_ALGORITHM=HS256`
- 新增: `ACCESS_TOKEN_EXPIRE_MINUTES=60`
- 移除: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`

**1.3 创建 `app/core/mongodb.py`**
```python
# MongoDB 连接管理
# - 启动时通过 motor.motor_asyncio.AsyncIOMotorClient 连接
# - 导出 get_database() → AsyncIOMotorDatabase
# - 导出 get_collection(name) → AsyncIOMotorCollection
# - 注册 FastAPI lifespan 事件（app startup → connect, shutdown → close）
```

**1.4 创建 `app/core/auth.py` (替代原 security.py)**
```python
# 本地 JWT 认证
# - create_access_token(user_id, email) → str
# - verify_token(credentials) → user_dict (本地验证 JWT，无外部 HTTP 调用)
# - hash_password(password) → str
# - verify_password(plain, hashed) → bool
```

### Phase 2: 数据模型转换 (约 3 小时)

**2.1 设计 MongoDB 文档结构**

将 PostgreSQL 关系表转换为 MongoDB 集合，处理关联关系：

| PG 表 → Mongo Collection | 关联处理策略 |
|--------------------------|-------------|
| `users` (新增) | 独立 collection |
| `app_settings` | 独立 collection，`user_id` 字段索引 |
| `devices` | 嵌入 `factory` 对象 (原 JOIN `factories`) |
| `factories` | 合并到 `devices.factory` 嵌入子文档 |
| `error_logs` | 嵌入 `device` 摘要 (sn, model)，或存 `device_id` |
| `maintenance_records` | 独立 collection，`device_id` + `date` 索引 |
| `case_library` | 独立 collection，`error_code` + 文本索引（替代 ilike） |
| `sync_jobs` | 独立 collection |
| `sync_remote_servers` | 独立 collection |
| `sync_remote_test_details` | 独立 collection，`server_id` + `detailed_flow` + `test_time` 复合索引 |

**关键关系处理原则：**
- **1:1 或 紧耦合 1:N** → 嵌入子文档 (如 `devices` 嵌入 `factory`)
- **独立查询的 1:N** → 存 `_id` 引用 (如 `error_logs` → `device_id`)
- **N:N** → 两边存引用数组

**2.2 更新 Pydantic 模型**

`app/models/request.py` 和 `app/models/response.py`:
- 将 `id: int` 改为 `id: str` (MongoDB ObjectId 的字符串表示)
- 新增 `PyObjectId` 类型用于 Pydantic v2 验证
- 新增用户注册/登录的请求模型

**2.3 创建索引初始化脚本**

```python
# migrations/mongo_indexes.py
# - 创建所有必要的索引（单字段、复合、文本）
# - 可通过 CLI 运行: python -m migrations.mongo_indexes
```

### Phase 3: 后端服务层重构 (约 5 小时)

**3.1 替换 `sync_service.py` 中的 `SupabaseAsyncClient`**
- 将 HTTPX 直接调 Supabase REST API → motor `find()`, `insert_many()`, `update_one()` with `upsert=True`
- `select()` → `collection.find(filter).sort().skip().limit()`
- `insert()` → `collection.insert_one()` / `insert_many()`
- `upsert()` → `collection.update_one(filter, {"$set": data}, upsert=True)`
- `update()` → `collection.update_one()` / `update_many()`
- `count_exact` → `collection.count_documents()`
- JOIN 查询 → MongoDB `$lookup` aggregation 或分步查询

**3.2 重写 `knowledge_graph.py`**
- 移除 `supabase-py` 同步 SDK 调用
- 替换为 motor 异步操作：
  - `find_similar_cases()`: MongoDB `$text` 搜索 或 `$regex` 替代 ilike
  - `get_device_test_logs()`: `$lookup` 从 `devices` collection 联表或分步查
  - `get_device_maintenance_history()`: 直接 `find()` + sort + limit
  - `get_device_by_sn()`: `find_one()` + `$lookup` factories 或读嵌入字段

**3.3 重写 `routers/settings.py`**
- 将 `supabase.table("app_settings")` 替换为 motor 操作
- `select` → `find_one({"user_id": user_id})`
- `insert` → `insert_one()`
- `update` → `update_one(..., {"$set": data})`

**3.4 新增 `routers/auth.py`**
```python
POST /api/auth/register  # 用户注册
POST /api/auth/login     # 用户登录 → 返回 JWT access_token
GET  /api/auth/me        # 获取当前用户信息
```

### Phase 4: 前端重构 (约 4 小时)

**4.1 重写 `src/api/supabase.ts` → `src/api/auth.ts`**
- 移除 `@supabase/supabase-js` 依赖
- 实现 `signIn(email, password)` → `POST /api/auth/login`
- 实现 `signUp(email, password)` → `POST /api/auth/register`
- 实现 `signOut()` → 清除本地 token
- 实现 `getAccessToken()` → 从 `localStorage` 读取 JWT
- 移除 `fetchErrorLogs()` (未使用，直接删除)

**4.2 更新 `src/contexts/AuthContext.tsx`**
- 移除 `supabase.auth.onAuthStateChange` 监听
- 替换为自定义 session 管理：
  - `signIn` → 调 `authApi.signIn()`, 存 token 到 localStorage
  - `signUp` → 调 `authApi.signUp()`
  - `signOut` → 清除 localStorage token
  - 初始化时从 localStorage 恢复 token, 调 `GET /api/auth/me` 验证有效性

**4.3 更新 `src/api/fastapi.ts`**
- `getAccessToken()` 从 supabase 改为读 localStorage
- 其余不变（仍然是 Bearer token 模式）

**4.4 清理**
- 移除 `@supabase/supabase-js` 从 `package.json`
- 移除 `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` 环境变量
- 更新 `src/vite-env.d.ts` 类型声明
- 删除 `src/api/supabase.ts`

### Phase 5: 测试与验证 (约 3 小时)

**5.1 更新后端测试**
- `conftest.py`: 新增 `mock_mongodb` fixture, 替换 `mock_supabase_client`
- `test_routers.py`: 更新 auth mock, 测试新的 auth 路由
- `test_sync_service.py`: mock motor 操作

**5.2 新增测试**
- `test_auth.py`: 注册/登录/JWT 验证的单元测试
- `test_mongodb.py`: MongoDB 连接和 CRUD 集成测试

**5.3 数据迁移脚本**
- 创建 `migrations/supabase_to_mongodb.py`:
  - 从 Supabase 导出所有表数据
  - 转换为 MongoDB 文档格式
  - 处理关系转换（JOIN → 嵌入或引用）
  - 写入 MongoDB

**5.4 端到端验证**
- 启动 MongoDB（本地或 Atlas）
- 运行数据迁移
- 启动后端 → 验证所有 API 端点
- 启动前端 → 验证登录/注册/数据展示/同步功能

---

## 风险与注意事项

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| JOIN 查询转换为 MongoDB 可能性能下降 | MEDIUM | 合理使用嵌入文档减少 $lookup；对高频查询字段建索引 |
| `ilike` 模糊搜索不可用 | MEDIUM | 使用 MongoDB `$text` 索引 + `$regex`，或集成全文搜索引擎 |
| Auth 从外部服务变为本地管理 | HIGH | 确保 JWT secret 强随机；考虑 refresh token 机制；密码 bcrypt 哈希 |
| `upsert` 的 `ignore_duplicates` 语义差异 | LOW | MongoDB `updateOne` + `upsert: true` 默认为 merge 行为；显式处理冲突 |
| 数据迁移中的关系转换可能丢失数据 | HIGH | 先在测试环境验证；保留 Supabase 备份直到迁移确认无误 |
| 前端 session 管理从 supabase-js 变为手动 | MEDIUM | 实现 token 自动刷新；处理 token 过期时的 UX |

---

## 工作量估算

| 阶段 | 估时 | 优先级 |
|------|------|--------|
| Phase 1: 基础设施准备 | 2h | P0 - 阻塞所有后续 |
| Phase 2: 数据模型转换 | 3h | P0 - 阻塞服务层 |
| Phase 3: 后端服务层重构 | 5h | P0 - 核心变更 |
| Phase 4: 前端重构 | 4h | P1 |
| Phase 5: 测试与验证 | 3h | P1 |
| **总计** | **~17h** | |

---

## 待确认问题

1. **MongoDB 部署方式？** MongoDB Atlas (云) 还是自托管 (Docker/服务器)？
2. **是否需要保留 Supabase Auth 作为 Auth Provider？** 还是完全自建 JWT 认证？
3. **是否有已有的 MongoDB 实例？** 集群配置、备份策略如何？
4. **数据迁移是否需要零停机？** 是否需要双写过渡期？
5. **是否需要同时支持 MongoDB 和 Supabase？** 通过 feature flag 渐进式迁移？

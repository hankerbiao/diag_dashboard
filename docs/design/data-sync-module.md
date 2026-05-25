# 第三方数据采集/同步模块 详细设计

> 版本: v1.1 | 日期: 2026-05-25 | 作者: WeaveEye 团队

---

## 1. 概述

### 1.1 背景

生产测试系统（`10.2.68.103`）管理服务器测试全流程数据。当前需要通过人工登录三方系统查看测试进度和结果，效率低且无法与本地诊断系统联动。本模块将三方数据定时同步到本地，提供统一查询入口。

### 1.2 目标

- 从三方系统拉取服务器列表及测试详情，存入本地 Supabase
- 支持按 `productModels`、`serverSN` 等字段搜索过滤
- 支持手动触发同步 + 定时自动同步
- 同步失败可恢复，不产生重复数据
- 前端提供数据查看和同步管理页面

### 1.3 三方 API 说明

| 接口 | 用途 | 方法 | 分页参数 |
|------|------|------|----------|
| `/stepsmanagement/monitor/queryTestingServers.action` | 获取服务器列表（含 SN） | POST | `page`, `limit`（响应含 `count`, `total`） |
| `/stepsmanagement/resultInfo/queryTestList.action` | 获取某 SN 的测试详情 | POST | `start`, `limit`（响应含 `total`） |

---

## 2. 数据库设计

### 2.1 ER 图

```
┌──────────────────────────────────┐
│  sync_remote_servers             │
├──────────────────────────────────┤
│ id (PK, UUID)                    │
│ server_sn (UNIQUE, TEXT)         │──┐
│ order_id (TEXT)                  │  │
│ model (TEXT)                     │  │   ┌──────────────────────────────────────────┐
│ product_models (TEXT)            │  │   │  sync_remote_test_details                │
│ host_ip (TEXT)                   │  │   ├──────────────────────────────────────────┤
│ bmc_ip4 (TEXT)                   │  │   │ id (PK, UUID)                            │
│ bmc_ip6 (TEXT)                   │  │   │ server_id (FK → servers.id)              │
│ position (TEXT)                  │  │   │ server_sn (TEXT, 冗余)                   │
│ logical (TEXT)                   │  ├──▶│ detailed_flow (TEXT)                     │
│ alarm (INTEGER)                  │  │   │ test_time (TIMESTAMPTZ)                  │
│ server_state (TEXT)              │  │   │ ─────────────────────────                │
│ test_items (TEXT)                │  │   │ UNIQUE(server_id, detailed_flow,         │
│ next_item (TEXT)                 │  │   │         test_time)  ◀── 复合唯一约束     │
│ item_begin_time (TIMESTAMPTZ)    │  │   │ ─────────────────────────                │
│ customer_id (TEXT)               │  │   │ big_flow (TEXT)                          │
│ customer_name (TEXT)             │  │   │ log_path (TEXT)                          │
│ sales_receipts (TEXT)            │  │   │ decision (TEXT)                          │
│ promised_date (TEXT)             │  │   │ server_test_result (TEXT)                │
│ maintenance_status (TEXT)        │  │   │ mes_record (TEXT)                        │
│ bmc_user_name (TEXT)             │  │   │ fault_type1 (TEXT)                       │
│ bmc_password (TEXT)              │  │   │ fault_type2 (TEXT)                       │
│ final_operation (TEXT)           │  │   │ fault_type3 (TEXT)                       │
│ customized_system (TEXT)         │  │   │ mes_remarks (TEXT)                       │
│ synced_at (TIMESTAMPTZ)          │  │   │ mes_time (TIMESTAMPTZ)                   │
│ created_at (TIMESTAMPTZ)         │  │   │ synced_at (TIMESTAMPTZ)                  │
│ updated_at (TIMESTAMPTZ)         │  │   │ created_at (TIMESTAMPTZ)                 │
└──────────────────────────────────┘  │   └──────────────────────────────────────────┘
                                      │
                                      │   ┌──────────────────────────────────────────┐
                                      │   │  sync_jobs (同步日志, 极简版)             │
                                      │   ├──────────────────────────────────────────┤
                                      │   │ id (PK, UUID)                            │
                                      │   │ status (TEXT) — running / success / failed│
                                      │   │ started_at / finished_at (TIMESTAMPTZ)    │
                                      │   │ servers_total / servers_new (INTEGER)     │
                                      │   │ details_total / details_new (INTEGER)     │
                                      │   │ error_message (TEXT)                     │
                                      │   └──────────────────────────────────────────┘
                                      │
                                      │ 现有表 ─────────────────────────────────────┐
                                      │  public.devices                             │
                                      │  ┌──────────────────────────────────────┐   │
                                      │  │ sn (UNIQUE, TEXT) — 格式不同          │   │
                                      │  └──────────────────────────────────────┘   │
                                      └─────────────────────────────────────────────┘
```

### 2.2 建表语句

```sql
-- ============================================================
-- 数据采集同步模块 — 数据库迁移 0002
-- ============================================================

-- 2.1 同步服务器列表（对应三方 API 1 返回字段）
CREATE TABLE public.sync_remote_servers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_sn           TEXT NOT NULL UNIQUE,          -- 三方系统的 SN，唯一标识
    order_id            TEXT NOT NULL DEFAULT '',
    model               TEXT NOT NULL DEFAULT '',
    product_models      TEXT NOT NULL DEFAULT '',
    host_ip             TEXT NOT NULL DEFAULT '',
    bmc_ip4             TEXT NOT NULL DEFAULT '',
    bmc_ip6             TEXT NOT NULL DEFAULT '',
    position            TEXT NOT NULL DEFAULT '',
    logical             TEXT NOT NULL DEFAULT '',
    alarm               INTEGER NOT NULL DEFAULT 0,    -- API 返回数字，如 3
    server_state        TEXT NOT NULL DEFAULT '',      -- API 返回为字符串 "2"，保留 TEXT 以兼容后续变更
    test_items          TEXT NOT NULL DEFAULT '',
    next_item           TEXT NOT NULL DEFAULT '',
    item_begin_time     TIMESTAMPTZ,
    customer_id         TEXT NOT NULL DEFAULT '',
    customer_name       TEXT NOT NULL DEFAULT '',
    sales_receipts      TEXT NOT NULL DEFAULT '',
    promised_date       TEXT NOT NULL DEFAULT '',
    maintenance_status  TEXT NOT NULL DEFAULT '',
    bmc_user_name       TEXT NOT NULL DEFAULT '',
    bmc_password        TEXT NOT NULL DEFAULT '',
    final_operation     TEXT NOT NULL DEFAULT '',
    customized_system   TEXT NOT NULL DEFAULT '',
    synced_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引：核心搜索字段
CREATE INDEX idx_sync_servers_sn              ON public.sync_remote_servers(server_sn);
CREATE INDEX idx_sync_servers_product_models   ON public.sync_remote_servers(product_models);
CREATE INDEX idx_sync_servers_customer_id      ON public.sync_remote_servers(customer_id);
CREATE INDEX idx_sync_servers_server_state     ON public.sync_remote_servers(server_state);
CREATE INDEX idx_sync_servers_order_id         ON public.sync_remote_servers(order_id);

-- 2.2 同步测试详情（对应三方 API 2 返回字段，一对多关联服务器）
-- 核心去重策略：复合唯一约束 (server_id, detailed_flow, test_time)
-- 同一个服务器 + 同一个测试流程 + 同一个测试时间 = 同一条数据，避免重复采集
CREATE TABLE public.sync_remote_test_details (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id           UUID NOT NULL REFERENCES public.sync_remote_servers(id) ON DELETE CASCADE,
    server_sn           TEXT NOT NULL,                 -- 冗余列，方便查询免 JOIN
    big_flow            TEXT NOT NULL DEFAULT '',
    detailed_flow       TEXT NOT NULL DEFAULT '',
    log_path            TEXT NOT NULL DEFAULT '',
    decision            TEXT NOT NULL DEFAULT '',
    server_test_result  TEXT NOT NULL DEFAULT '',       -- "成功" / "失败"
    test_time           TIMESTAMPTZ NOT NULL,           -- 测试时间，复合唯一键的一部分
    mes_record          TEXT NOT NULL DEFAULT '',
    fault_type1         TEXT NOT NULL DEFAULT '',
    fault_type2         TEXT NOT NULL DEFAULT '',
    fault_type3         TEXT NOT NULL DEFAULT '',
    mes_remarks         TEXT NOT NULL DEFAULT '',
    mes_time            TIMESTAMPTZ,
    synced_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 复合唯一约束：保证不重复采集同一条测试记录
    CONSTRAINT uq_test_detail UNIQUE (server_id, detailed_flow, test_time)
);

-- 索引
CREATE INDEX idx_sync_details_server_id   ON public.sync_remote_test_details(server_id);
CREATE INDEX idx_sync_details_server_sn   ON public.sync_remote_test_details(server_sn);
CREATE INDEX idx_sync_details_test_result ON public.sync_remote_test_details(server_test_result);
CREATE INDEX idx_sync_details_test_time   ON public.sync_remote_test_details(test_time DESC);

-- 2.3 同步任务历史（追踪每次同步执行状态，极简版）
CREATE TABLE public.sync_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status              TEXT NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'success', 'failed')),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ,
    servers_total       INTEGER NOT NULL DEFAULT 0,     -- 本次拉取的服务器总数
    servers_new         INTEGER NOT NULL DEFAULT 0,     -- 新增服务器数
    details_total       INTEGER NOT NULL DEFAULT 0,     -- 本次拉取的测试详情总数
    details_new         INTEGER NOT NULL DEFAULT 0,     -- 新增测试详情数（跳过重复后的实际插入数）
    error_message       TEXT NOT NULL DEFAULT ''
);

CREATE INDEX idx_sync_jobs_started_at ON public.sync_jobs(started_at DESC);
```

### 2.3 设计决策说明

| 决策 | 理由 |
|------|------|
| `UNIQUE(server_id, detailed_flow, test_time)` 复合去重 | 同一服务器 + 同一测试流程 + 同一时间戳 = 同一条数据，re-sync 时 DB 自动跳过已存在记录，无需应用层判断 |
| `server_sn` 冗余存储 | 查询某 SN 的测试详情时免 JOIN，减少复杂度 |
| `alarm` 用 `INTEGER` | API 返回值是数字 `3`，非字符串 |
| `server_state` 保留 `TEXT` | 当前返回 `"2"` 是字符串格式，后续可能变为非数字值 |
| 不与 `public.devices` 合并 | 三方 SN（`1000202602250011`）与本地 SN（`6102263004319419`）格式不同，独立存储为远程快照 |
| sync_jobs 极简化 | v1 只追踪 running/success/failed + 新增数量，不追踪断点、跳过数、触发方式，后续按需扩展 |

### 2.4 去重策略（简化版）

```
同步触发
  │
  ├── 1. 拉取 API 1 服务器列表（全量分页）
  │      └── Upsert 到 sync_remote_servers
  │           ON CONFLICT (server_sn) DO UPDATE
  │
  └── 2. 对每个服务器，拉取 API 2 测试详情（全量分页）
         │
         └── 逐条 Upsert:
              ON CONFLICT (server_id, detailed_flow, test_time) DO NOTHING
              ├── 冲突 → DB 自动跳过（已存在）
              └── 不冲突 → 插入新记录
```

**核心思路：不判断增量，每次都全量拉取。去重完全交给数据库的复合唯一约束处理。**

- 简单可靠：无需维护 `last_test_time`、断点等复杂状态
- 不会遗漏：即使之前同步中断，下次全量拉取自动补齐
- 性能可接受：API 2 单台最多几百条，全量拉取开销在毫秒级
- 后续优化：当单台服务器数据量 > 5000 条时，再考虑加增量水印

---

## 3. 后端设计

### 3.1 模块结构

```
diag_backend/app/
├── core/
│   └── config.py          # 新增 3 个配置项
├── services/
│   └── sync_service.py    # [新文件] 核心同步逻辑
├── routers/
│   └── sync.py            # [新文件] 同步 API 路由
├── models/
│   └── response.py        # 新增 sync 相关响应模型
└── main.py                # 注册 sync 路由
```

### 3.2 配置项

`diag_backend/app/core/config.py` 新增：

```python
class Settings(BaseSettings):
    # ... 现有配置 ...

    # Sync Module
    sync_api_base_url: str = "http://10.2.68.103"
    sync_api_timeout: int = 30          # 单次请求超时秒数
    sync_max_concurrency: int = 5       # 同时请求 API 2 的最大并发数
    sync_max_retries: int = 3           # 单次请求最大重试次数

    class Config:
        env_file = ".env"
```

`.env` 新增：

```bash
# 三方数据同步
SYNC_API_BASE_URL=http://10.2.68.103
SYNC_API_TIMEOUT=30
SYNC_MAX_CONCURRENCY=5
SYNC_MAX_RETRIES=3
```

### 3.3 核心服务：`sync_service.py`

```
class SyncService
├── __init__(settings) → 初始化 httpx.AsyncClient
├── _create_job(triggered_by) → sync_jobs 记录
├── _update_job(job_id, **fields) → 更新 job 状态
│
├── fetch_servers(page, limit) → list[dict]
│   └── POST queryTestingServers.action
│       请求: page, limit, customerID, salesReceipts, orderID
│       响应解析: data[], count, total
│       分页终止条件: len(data) == 0 或 page * limit >= total
│
├── fetch_test_details(serverSN, start=0, limit=500) → list[dict]
│   └── POST queryTestList.action
│       请求: start, limit, serverSN, customerID
│       循环请求直到: len(batch) < limit (数据取完)
│
├── sync_all() → job_id
│   ├── 1. asyncio.Lock 防并发
│   ├── 2. CREATE sync_jobs (status=running)
│   ├── 3. 分页拉取 API 1，每页批量 Upsert 到 sync_remote_servers
│   ├── 4. 对每个 server_sn:
│   │   ├── asyncio.Semaphore 控制并发
│   │   ├── 分页拉取 API 2（全量，不做增量判断）
│   │   ├── Upsert 到 sync_remote_test_details (ON CONFLICT DO NOTHING)
│   │   └── 统计 details_new
│   ├── 5. UPDATE sync_jobs (status=success)
│   └── 6. except → UPDATE sync_jobs (status=failed, error_message)
│
├── get_servers(search_sn, search_product_models, page, limit) → PaginatedResponse
│   └── Supabase 查询 sync_remote_servers, ILIKE 模糊匹配
│
├── get_test_details(server_sn, page, limit) → PaginatedResponse
│   └── Supabase 查询 sync_remote_test_details WHERE server_sn = ?
│
├── get_jobs(page, limit) → 查询 sync_jobs 列表
│
└── get_latest_job_status() → 最新同步状态（供前端轮询）
```

**关键实现细节：**

```python
# 1. 并发控制：防止同时运行多个同步
self._sync_lock = asyncio.Lock()

async def sync_all(self, triggered_by: str = "manual") -> str:
    if self._sync_lock.locked():
        latest = await self._get_running_job()
        if latest:
            return latest["id"]
    async with self._sync_lock:
        ...

# 2. API 2 真分页（处理 >1000 条的场景）
async def fetch_test_details(self, server_sn: str) -> list[dict]:
    all_data = []
    start = 0
    limit = 500
    while True:
        resp = await self._client.post(
            "/stepsmanagement/resultInfo/queryTestList.action",
            data={"start": start, "limit": limit, "serverSN": server_sn, "customerID": ""}
        )
        batch = resp.json()["data"]
        all_data.extend(batch)
        if len(batch) < limit:
            break
        start += limit
    return all_data

# 3. Upsert 去重：复合唯一约束自动跳过重复
# servers: ON CONFLICT (server_sn) DO UPDATE
# test_details: ON CONFLICT (server_id, detailed_flow, test_time) DO NOTHING
await supabase.table("sync_remote_test_details").upsert(
    records,
    on_conflict="server_id,detailed_flow,test_time",
    ignore_duplicates=True
).execute()

# 4. 并发请求 API 2（Semaphore 限流）
semaphore = asyncio.Semaphore(self.max_concurrency)

async def _sync_one_server(sn: str, sid: str):
    async with semaphore:
        details = await self.fetch_test_details(sn)
        return await self._upsert_details(sid, sn, details)

tasks = [_sync_one_server(sn, sid) for sn, sid in server_id_map.items()]
results = await asyncio.gather(*tasks, return_exceptions=True)
# 单个 SN 失败不影响其他，异常计入 error_message
```

### 3.4 API 路由：`routers/sync.py`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/api/sync/trigger` | JWT | 手动触发同步，立即返回 `{job_id}`，后台执行 |
| `GET` | `/api/sync/servers` | JWT | 查询服务器列表，支持 `search_sn`, `search_product_models`, `page`, `limit` |
| `GET` | `/api/sync/servers/{server_sn}/test-details` | JWT | 查询某服务器测试详情，支持 `page`, `limit` |
| `GET` | `/api/sync/jobs` | JWT | 同步历史记录，支持 `page`, `limit` |
| `GET` | `/api/sync/status` | JWT | 最新同步状态（供前端轮询） |

路由注册在 `main.py`：

```python
from .routers import sync

app.include_router(sync.router, prefix="/api")
```

### 3.5 响应模型

在 `models/response.py` 新增：

```python
class SyncServerResponse(BaseModel):
    id: str
    server_sn: str
    order_id: str
    model: str
    product_models: str
    host_ip: str
    server_state: str
    test_items: str
    customer_name: str
    alarm: int
    synced_at: datetime

class SyncTestDetailResponse(BaseModel):
    id: str
    server_sn: str
    detailed_flow: str
    server_test_result: str
    test_time: datetime
    fault_type1: str
    fault_type2: str
    fault_type3: str

class SyncJobResponse(BaseModel):
    id: str
    status: str                    # running / success / failed
    started_at: datetime
    finished_at: Optional[datetime]
    servers_total: int
    servers_new: int
    details_total: int
    details_new: int
    error_message: str

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    limit: int
```

---

## 4. 前端设计

### 4.1 新增/修改文件

```
diag_frontend/src/
├── types/index.ts                           # [修改] 新增 'sync' tab + 接口定义
├── api/fastapi.ts                           # [修改] 新增 syncApi
├── App.tsx                                  # [修改] 渲染 SyncManagementTab
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx                      # [修改] 导航新增「数据同步管理」
│   │   └── Header.tsx                       # [修改] TAB_TITLES 新增 sync 条目
│   └── sync/                                # [新目录]
│       ├── SyncManagementTab.tsx            # [新文件] 主页面（搜索+表格+展开+同步按钮）
│       └── SyncTriggerButton.tsx            # [新文件] 触发按钮 + 轮询状态
```

### 4.2 TypeScript 类型

```typescript
// types/index.ts — NavigationTab 新增 'sync'
export type NavigationTab = 'diagnosis' | 'error_logs' | 'settings' | 'sync';

// 同步数据接口
export interface SyncServer {
  id: string;
  server_sn: string;
  order_id: string;
  model: string;
  product_models: string;
  host_ip: string;
  server_state: string;
  test_items: string;
  customer_name: string;
  alarm: number;
  synced_at: string;
}

export interface SyncTestDetail {
  id: string;
  server_sn: string;
  detailed_flow: string;
  server_test_result: string;
  test_time: string;
  fault_type1: string;
  fault_type2: string;
  fault_type3: string;
}

export interface SyncJob {
  id: string;
  status: 'running' | 'success' | 'failed';
  started_at: string;
  finished_at: string | null;
  servers_total: number;
  servers_new: number;
  details_total: number;
  details_new: number;
  error_message: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}
```

### 4.3 API 客户端

```typescript
// api/fastapi.ts — 新增 syncApi
export const syncApi = {
  async getServers(params: {
    search_sn?: string;
    search_product_models?: string;
    page?: number;
    limit?: number;
  }): Promise<ApiResponse<PaginatedResponse<SyncServer>>> {
    const query = new URLSearchParams();
    if (params.search_sn) query.set('search_sn', params.search_sn);
    if (params.search_product_models) query.set('search_product_models', params.search_product_models);
    if (params.page) query.set('page', String(params.page));
    if (params.limit) query.set('limit', String(params.limit));
    return fetchApi(`/api/sync/servers?${query.toString()}`);
  },

  async getTestDetails(
    serverSn: string,
    params?: { page?: number; limit?: number }
  ): Promise<ApiResponse<PaginatedResponse<SyncTestDetail>>> {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    return fetchApi(`/api/sync/servers/${serverSn}/test-details?${query.toString()}`);
  },

  async triggerSync(): Promise<ApiResponse<{ job_id: string }>> {
    return fetchApi('/api/sync/trigger', { method: 'POST' });
  },

  async getSyncStatus(): Promise<ApiResponse<SyncJob | null>> {
    return fetchApi('/api/sync/status');
  },

  async getSyncJobs(params?: { page?: number; limit?: number }): Promise<ApiResponse<PaginatedResponse<SyncJob>>> {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.limit) query.set('limit', String(params.limit));
    return fetchApi(`/api/sync/jobs?${query.toString()}`);
  },
};
```

### 4.4 组件设计

#### SyncManagementTab（主容器）

```
┌─────────────────────────────────────────────────────────┐
│  第三方数据同步管理                                       │
│                                                         │
│  ┌─────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ 触发同步     │  │ 上次同步: 成功   │  │ 最近5条记录   │ │
│  │ [按钮+轮询]  │  │ 时间: 10:15     │  │ ...          │ │
│  └─────────────┘  └─────────────────┘  └──────────────┘ │
│                                                         │
│  搜索: [serverSN____] [productModels____] [搜索按钮]     │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ 服务器列表                                           ││
│  │ ┌──────────────────────────────────────────────────┐││
│  │ │ SN │ 型号 │ 产品型号 │ IP │ 状态 │ 测试项 │ ... │││
│  │ │────│──────│─────────│────│─────│───────│─────││││
│  │ │ ▸ 10002... │ TL550FS-B │ ... │ ► 展开           ││││
│  │ └──────────────────────────────────────────────────┘││
│  │                    ◀ 1/5 ▶                          ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

**状态管理：**
- `searchSN: string` — SN 搜索关键词
- `searchProductModels: string` — 型号搜索关键词
- `serverPage: number` — 服务器列表分页
- `expandedSN: string | null` — 当前展开的服务器 SN（加载测试详情）
- `syncStatus: SyncJob | null` — 最新同步状态
- 搜索变化时自动请求（useEffect deps），输入做 300ms debounce

#### ServerTable

- 列：server_sn, model, product_models, host_ip, server_state, test_items, customer_name, synced_at
- 行首有展开按钮 `▸`，点击后展开 `<TestDetailsPanel />`
- 展开时调用 `syncApi.getTestDetails(serverSn)`
- 测试结果为"失败"的行高亮红色

#### TestDetailsPanel

- 嵌套表格：detailed_flow, server_test_result, test_time, fault_type1/2/3, decision
- 支持独立分页

#### SyncTriggerButton

```
状态机:
  IDLE ────[点击]───→ SYNCING ────[5s轮询]───→ SUCCESS / FAILED
                                         │
                                         └── 错误信息展示
```

- 按钮点击 → `syncApi.triggerSync()` → 获得 `job_id`
- 每 5 秒调用 `syncApi.getSyncStatus()` 直到 `status !== 'running'`
- 按钮在 `SYNCING` 状态时禁用，显示转圈动画
- 成功后显示 "同步完成: 新增 X 台服务器, Y 条测试记录"
- 失败后显示错误信息，按钮恢复可点击

### 4.5 导航集成

**Sidebar.tsx** — 在"功能导航"区域 `navItems` 末尾新增：

```tsx
{ icon: <RefreshCw className="w-4 h-4" />, label: '数据同步管理', tab: 'sync' }
```

**Header.tsx** — `TAB_TITLES` 新增条目：

```tsx
sync: '第三方数据同步管理',
```

**App.tsx** — 新增渲染分支：

```tsx
import SyncManagementTab from './components/sync/SyncManagementTab';

{activeTab === 'sync' && <SyncManagementTab />}
```

---

## 5. 同步流程时序

```
用户/Frontend               FastAPI Router              SyncService               三方 API
    │                           │                           │                        │
    │  POST /api/sync/trigger   │                           │                        │
    │──────────────────────────▶│                           │                        │
    │                           │  sync_all() [background]  │                        │
    │                           │──────────────────────────▶│                        │
    │  {job_id: "xxx"}          │                           │                        │
    │◀──────────────────────────│                           │                        │
    │                           │                           │  [Acquire Lock]        │
    │                           │                           │  CREATE sync_jobs      │
    │                           │                           │                        │
    │                           │                           │  page=1 ──────────────▶│
    │                           │                           │  ◀── {data[], total}  │
    │                           │                           │  Upsert servers        │
    │                           │                           │                        │
    │                           │                           │  page=2 ──────────────▶│
    │                           │                           │  ◀── {data[], total}  │
    │                           │                           │  ...                   │
    │                           │                           │                        │
    │                           │                           │  ═══ 对每个 SN ═══     │
    │                           │                           │  SN=001 start=0 ──────▶│
    │                           │                           │  ◀── {data[]}         │
    │                           │                           │  SN=001 start=500 ────▶│
    │                           │                           │  ◀── {data[]}         │
    │                           │                           │  Upsert details        │
    │                           │                           │  (Semaphore 控制并发)   │
    │                           │                           │  ...                   │
    │                           │                           │                        │
    │                           │                           │  UPDATE job=success    │
    │                           │                           │  [Release Lock]        │
    │                           │                           │                        │
    │  GET /api/sync/status     │                           │                        │
    │──────────────────────────▶│──────────────────────────▶│                        │
    │  {status: "success", ...} │                           │                        │
    │◀──────────────────────────│                           │                        │
```

---

## 6. 错误处理

### 6.1 策略

| 级别 | 场景 | 处理 |
|------|------|------|
| 致命 | 网络不通、DNS 解析失败 | 立即终止，job.status = `failed`，记录 error_message |
| 严重 | API 1 某页请求超时 | 重试 3 次（指数退避 1s/2s/4s），仍失败则 job = `failed` |
| 可恢复 | 单个 SN 的 API 2 请求失败 | 跳过该 SN，追加到 error_message，继续处理下一个 |
| 可恢复 | 某条 upsert 失败 | 跳过该条，追加 error_message，继续下一条 |

### 6.2 请求重试

```python
import asyncio
from httpx import HTTPStatusError, TimeoutException

async def _post_with_retry(self, url: str, data: dict, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            resp = await self._client.post(url, data=data, timeout=30.0)
            resp.raise_for_status()
            return resp.json()
        except (HTTPStatusError, TimeoutException) as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
```

---

## 7. 安全考虑

| 措施 | 说明 |
|------|------|
| JWT 认证 | 所有 `/api/sync/*` 路由通过 `Depends(get_current_user)` 保护 |
| 密码字段处理 | `bmc_password` 字段暂存原值，后续可考虑加密存储 |
| 内网地址 | `sync_api_base_url` 默认 `10.2.68.103` 仅内网可达，生产部署需确认网络连通性 |
| 速率限制 | `asyncio.Semaphore(5)` 限制并发请求三方 API |
| SQL 注入 | 使用 Supabase SDK 参数化查询，不拼接 SQL |

---

## 8. 实施计划

### Phase 1: 数据库迁移
- 文件：`supabase/migrations/0002_sync_tables.sql`
- 风险：低 | 验证：执行 SQL

### Phase 2: 后端配置 + 模型 + 服务
- 修改：`config.py`, `.env`, `response.py`
- 新增：`services/sync_service.py`, `routers/sync.py`
- 修改：`main.py`（注册路由）
- 风险：中（依赖三方 API 连通性）

### Phase 3: 前端集成
- 修改：`types/index.ts`, `api/fastapi.ts`
- 新增：`SyncManagementTab.tsx`, `SyncTriggerButton.tsx`
- 修改：`App.tsx`, `Sidebar.tsx`, `Header.tsx`
- 风险：低

---

## 9. 模块解耦与扩展设计

### 9.1 是否独立部署？

**建议：v1 不独立部署，但通过 DataSource 抽象接口为未来解耦留好切口。**

```
当前架构（集成模式）:                未来架构（解耦模式）:
                                    
  FastAPI 进程                          sync-service (独立进程/容器)
  ┌──────────────────┐                 ┌──────────────────────────┐
  │  diagnosis 路由   │                 │  sync-service             │
  │  error_logs 路由  │                 │  ├── Cron 定时触发        │
  │  settings 路由    │                 │  ├── DataSource 注册表    │
  │  sync 路由 ───────│─ sync_service   │  └── → 直写 Supabase      │
  │            │      │                 └──────────────────────────┘
  │  llm_service      │                           │
  └──────────────────┘                 ┌───────────┴───────────┐
                                       │  Supabase              │
                                       │  sync_remote_*  表     │
                                       └───────────────────────┘
                                               ▲
  FastAPI 进程                                 │ 只读查询
  ┌──────────────────┐                 FastAPI 进程
  │  diagnosis/error  │               ┌──────────────────┐
  │  /settings 路由   │               │  sync 查询路由     │
  └──────────────────┘               └──────────────────┘
```

### 9.2 DataSource 抽象

当前只有一个数据源（`10.2.68.103`），但设计时应做抽象：

```python
from abc import ABC, abstractmethod

class DataSource(ABC):
    """三方数据源抽象接口。每接入一个新平台，实现此接口即可。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称，如 'steps_management'"""
        ...

    @abstractmethod
    async def fetch_servers(self, page: int, limit: int) -> tuple[list[dict], int]:
        """获取服务器列表，返回 (data, total)"""
        ...

    @abstractmethod
    async def fetch_test_details(self, server_sn: str, start: int, limit: int) -> tuple[list[dict], int]:
        """获取某 SN 的测试详情，返回 (data, total)"""
        ...

    @abstractmethod
    def to_server_record(self, raw: dict) -> dict:
        """将原始 JSON 转为 sync_remote_servers 表字段"""
        ...

    @abstractmethod
    def to_detail_records(self, server_id: str, raw_list: list[dict]) -> list[dict]:
        """将原始 JSON 列表转为 sync_remote_test_details 表字段"""
        ...


class StepsManagementSource(DataSource):
    """10.2.68.103 数据源"""
    name = "steps_management"

    async def fetch_servers(self, page, limit):
        resp = await self._post("/stepsmanagement/monitor/queryTestingServers.action", ...)
        return resp["data"], resp["total"]

    # ...
```

**好处：**
- 新增一个三方平台只需新增一个 `DataSource` 子类，`SyncService` 代码零改动
- `SyncService` 接收 `list[DataSource]`，遍历执行 `sync_all(source)`
- 后续迁移到独立服务时，`DataSource` 接口无需修改，直接复用

### 9.3 升级为独立服务的时机

| 触发条件 | 说明 |
|----------|------|
| 数据源 > 3 个 | 每个源有独立的认证、重试策略、调度周期 |
| 同步耗时 > 5 分钟 | 长时间同步不应阻塞 FastAPI 进程 |
| 需要独立的调度策略 | 不同数据源不同频率（A 每 10 分钟、B 每小时） |
| 需要独立扩展 | sync 服务是 CPU/IO 密集型，主 API 是延迟敏感型 |

### 9.4 当前建议

**v1：集成模式 + DataSource 抽象。** 把 `SyncService` 设计为可以注入多个 `DataSource`，但部署时和 FastAPI 同一个进程。这样开发量最小，后续要拆出来时只需：
1. 新建 `sync-service/` 目录
2. 把 `sync_service.py` + `DataSource` 子类移过去
3. 加上 APScheduler 做定时调度
4. FastAPI 端只保留只读查询路由 + 手动触发 API（通过 HTTP 调 sync-service）

---

## 10. 附录

### A. 与现有 `public.devices` 表的关系

| 对比项 | `devices.sn` | `sync_remote_servers.server_sn` |
|--------|-------------|-------------------------------|
| 格式 | `6102263004319419` | `1000202602250011` |
| 来源 | 本地录入/导入 | 三方 API 同步 |
| 用途 | 诊断系统的设备主数据 | 生产测试进度跟踪 |
| 关联 | — | 后续可建立 `devices.sn = sync_remote_servers.server_sn` 的映射关系（如果格式统一） |

当前阶段两个表独立运行，不建立 FK 关联。后续如果需要将三方测试数据关联到本地设备，可通过 SN 做应用层关联。

### B. 依赖变更

`requirements.txt` 新增：

```
httpx>=0.25.0          # 异步 HTTP 客户端（请求三方 API）
```

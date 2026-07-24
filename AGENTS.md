# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

**WeaveEye** — 基于 AI 的智能设备诊断与异常分析系统，前后端分离架构。

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS 4 | 端口 3000 |
| 后端 | FastAPI + Motor (MongoDB 异步驱动) | 端口 8000 |
| 数据库 | MongoDB (`10.17.154.252:27018`) | |
| 认证 | OA SSO + 应用 JWT (python-jose) | 仅开放 OA 登录 |
| AI | OpenAI / Gemini (兼容 API) | 智能诊断推理 |
| 知识库引擎 | RAGFlow | 文档解析与检索问答 |
| 文档 | VitePress | `docs/` 目录 |

## Development Commands

### Backend (`diag_backend/`)
```bash
cd diag_backend
uv pip install -r requirements.txt    # 安装依赖
uvicorn app.main:app --reload --port 8000  # 开发服务器
pytest                                 # 运行测试
pytest --cov=app --cov-report=term-missing  # 带覆盖率
```

### Frontend (`diag_frontend/`)
```bash
cd diag_frontend
npm install              # 安装依赖
npm run dev              # 开发服务器 (端口 3000, host 0.0.0.0)
npm run lint             # TypeScript 类型检查 (tsc --noEmit)
npm run build            # 生产构建
```

### Python 代码质量
```bash
ruff check .             # 代码检查
ruff format .            # 代码格式化
```

### 独立数据同步 (`scripts/`，不在 API 进程内执行)
```bash
pip install -r scripts/requirements.txt
cp scripts/sync_config.example.yaml scripts/sync_config.yaml

# 一键：SIMS 测试数据 + MES 维修记录 → MongoDB
python scripts/weaveeye_sync.py run
./scripts/run_sync.sh                    # 可配合 crontab

# 子命令
python scripts/weaveeye_sync.py sims --hours 24 --factory kunshan
python scripts/weaveeye_sync.py mes --sync-recent 1
```
详见 `scripts/README.md`。

## Architecture

### 后端分层

```
app/
├── main.py                    # FastAPI 入口, lifespan (MongoDB 连接 + 分析调度器启动)
├── core/
│   ├── config.py              # Pydantic Settings (MongoDB/JWT/AI/RAGFlow/Sync 配置)
│   ├── auth.py                # 应用 Bearer JWT 签发/验证
│   ├── mongodb.py             # Motor 异步连接管理
│   ├── mongodb_indexes.py     # 启动时自动创建索引 + seed 默认厂区数据
│   └── factory_config.py      # 读取 configs/factories.yaml (后端和脚本共享)
├── routers/
│   ├── auth.py                # POST /api/auth/oa/callback, GET /me
│   ├── diagnosis.py           # POST /api/diagnosis/sn, /error-log/{id}
│   ├── error_logs.py          # GET /api/error-logs/stats, /trend, /stats/yield
│   ├── analytics.py           # GET /api/analytics/insights (看板聚合数据)
│   ├── factories.py           # GET /api/factories (从 YAML 读取厂区列表)
│   ├── knowledge_base.py     # CRUD /api/knowledge-base/documents (本地 + RAGFlow)
│   ├── settings.py            # GET/PUT /api/settings (MongoDB app_settings)
│   └── sync.py                # GET /api/sync/servers*（MES 实时查询，只读）
├── services/
│   ├── llm_service.py         # OpenAI/Gemini LLM 调用封装 (含 mock 模式)
│   ├── ragflow_service.py     # RAGFlow API 封装 (数据集/文档/聊天助手 CRUD)
│   ├── knowledge_graph.py     # 知识图谱检索 (case_library, devices, error_logs, maintenance)
│   ├── analytics_service.py   # 看板数据后台预计算 + 快照缓存 (每小时调度)
│   └── mes_direct_service.py  # MES/SIMS 实时 HTTP 查询
├── models/
│   ├── auth.py                # 认证请求/响应 Pydantic 模型
│   ├── request.py             # 通用请求模型
│   └── response.py            # 通用响应模型
└── prompts/                   # AI 提示词模板

configs/
└── factories.yaml             # 厂区配置 (后端和独立同步脚本共享的数据源)
```

### 前端分层

```
src/
├── api/
│   ├── auth.ts                # OA 回调 + 应用 JWT 管理 (localStorage)
│   ├── fastapi.ts             # FastAPI HTTP 客户端 (diagnosisApi, settingsApi, syncApi)
│   └── index.ts               # 统一导出
├── components/
│   ├── auth/                  # AuthGuard, LoginPage, ParticleBackground
│   ├── layout/                # Sidebar, Header, Footer
│   ├── common/                # LoadingSpinner, ResultBadge, ThemeToggle
│   ├── diagnosis/             # 单机诊断 (DiagnosisInput, DiagnosisResult, ReferenceData)
│   ├── dashboard/             # 数据看板 (TrendDashboard, ModelStatisticsDashboard + 5 种图表)
│   ├── error-logs/            # 异常看板 (ErrorLogsTab, ErrorTable, SearchPanel, AnalysisModal, ServerDetailModal + 5 种图表)
│   ├── knowledge-base/        # 知识库管理 (KnowledgeBaseTab, DocCard, DocDetailDrawer, UploadZone)
│   └── settings/              # 设置页 (ApiConfig, KnowledgeBase)
├── contexts/
│   ├── AuthContext.tsx         # OA 回调、会话恢复与退出状态管理
│   └── ThemeContext.tsx        # 主题
├── hooks/                     # useChartTheme, useDebounce, useTypingAnimation
├── types/
│   ├── index.ts               # 共享 TS 类型 (camelCase)
│   └── analytics.ts           # 分析看板数据类型
├── data/mockData.ts           # 模拟数据
├── utils/serverState.ts       # 服务器状态枚举
└── App.tsx                    # ThemeProvider → AuthProvider → AuthGuard → AppContent
```

### 数据流

```
浏览器 → AuthContext (localStorage JWT)
              │
              ├── OA springboard → POST /api/auth/oa/callback → MongoDB.users
              │
              └── fetchApi() → Authorization: Bearer <token>
                      │
                      ├── /api/diagnosis/* → knowledge_graph + llm_service → MongoDB
                      ├── /api/analytics/* → analytics_service (预计算快照) → MongoDB
                      ├── /api/knowledge-base/* → 本地文件 + RAGFlow API
                      ├── /api/settings/* → MongoDB.app_settings
                      ├── /api/sync/servers* → MES 实时查询
                      ├── scripts/weaveeye_sync.py → MongoDB (sync_* collections)
                      ├── /api/factories/* → configs/factories.yaml
                      └── /api/error-logs/* → (当前为 mock 数据)
```

## MongoDB Collections

| Collection | 核心查询字段 | 用途 |
|-----------|-------------|------|
| `users` | `itcode` (unique, sparse) | OA 用户认证与 profile |
| `app_settings` | `user_id` (unique) | 用户设置 |
| `devices` | `sn` (unique) | 设备信息 |
| `error_logs` | `device_id` + `test_time` | 异常日志 |
| `maintenance_records` | `device_id` + `date` | 维修记录 |
| `case_library` | `error_code`, `root_cause` (text) | 案例库 |
| `sync_jobs` | `status` + `started_at`, `factory_id` + `started_at` | 同步任务记录 |
| `sync_remote_servers` | `factory_id`+`server_sn` (unique), `server_sn`, `product_models` | 远程服务器列表 |
| `sync_remote_test_details` | `factory_id`+`server_sn`+`test_time`, `factory_id`+`server_id`+`detailed_flow`+`test_time` | 远程测试明细 |
| `factory_sites` | `factory_id` (unique) | 厂区站点 (从 YAML seed) |
| `auto_sync_configs` | `factory_id` | （遗留）原 API 内自动同步配置，现由外部 cron + `weaveeye_sync.py` |
| `knowledge_documents` | `uploaded_at`, `title` | 知识库文档元数据 |
| `analytics_snapshots` | `computed_at` | 看板预计算结果缓存 |
| `diagnosis_cache` | `error_log_id` (unique) | 诊断缓存 |

索引在应用启动时通过 `mongodb_indexes.py` 自动创建（`create_index` 为幂等操作），同时 seed 默认厂区数据。

## Key Design Decisions

- **厂区配置**: 统一使用 `configs/factories.yaml` 管理厂区列表，后端 `factory_config.py` 和独立脚本 `scripts/sync_data.py` 均从此文件读取，单一数据源
- **RAGFlow 集成**: 知识库支持本地存储 + RAGFlow 自动同步双写。RAGFlow 为可选配置，未配置时不影响服务启动
- **看板缓存**: `analytics_service.py` 每小时后台预计算看板聚合数据写入 MongoDB 快照，前端直接读取避免实时聚合压力
- **MongoDB 关联策略**: 紧耦合的 1:1 关系用嵌入文档，独立查询的 1:N 用 `_id` 引用
- **认证**: OA payload 验签并按 `itcode` 落库，随后签发本地 Bearer JWT
- **数据同步**: 独立脚本 `scripts/weaveeye_sync.py`，由 crontab/运维机定期执行，API 不触发写入
- **ObjectId 处理**: 所有 MongoDB 自动生成的 `_id` 在 API 响应中转为字符串 `id` 字段
- **async/await**: 全链路异步 — Motor 驱动 + httpx.AsyncClient，无同步阻塞

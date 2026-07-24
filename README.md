# WeaveEye 智能诊断系统

<div align="center">

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript)](https://www.typescriptlang.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb)](https://www.mongodb.com/)

*基于 AI 的智能设备诊断与异常分析系统*

</div>

---

## 项目概览

WeaveEye 是前后端分离的智能诊断系统，提供设备 SN 深度诊断、异常日志分析、数据看板等功能，结合知识图谱与 LLM 进行推理。

### 技术架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   前端      │────►│   后端      │────►│  MongoDB    │
│ React+Vite  │     │  FastAPI    │     │             │
│  :3000      │     │  :8000      │     └─────────────┘
└─────────────┘     └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ LLM / RAGFlow│  （可选，经 .env 配置）
                    └─────────────┘
```

### 核心功能

| 模块 | 说明 |
|------|------|
| **SN 诊断** | 按序列号聚合设备信息、测试日志、维修记录与知识库，生成诊断结论 |
| **异常剖析** | 对单条异常日志下载原文、检索知识库并输出 AI 分析 |
| **数据看板** | 按厂区与时间范围展示直通率、问题类型等聚合指标 |
| **知识库** | 本地文档存储，可选对接 RAGFlow |
| **MES 实时查询** | 异常看板按厂区查询服务器与测试明细（直连厂区 MES API） |

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19、TypeScript、Vite 6、Tailwind CSS 4、Recharts |
| 后端 | FastAPI、Motor、Pydantic |
| 数据 | MongoDB |
| 认证 | OA SSO + 应用 Bearer JWT |
| AI | OpenAI / Gemini（兼容 API），可选 RAGFlow |

---

## 目录结构

```
diag_ai_analysis/
├── diag_backend/           # FastAPI 后端
│   ├── app/                # 应用代码（入口 app.main:app）
│   ├── configs/            # 厂区配置 factories.yaml
│   ├── docs/               # 后端 VitePress 文档（可选）
│   └── requirements.txt
├── diag_frontend/          # React 前端
├── docker/                 # Docker Compose 部署
├── deploy/                 # 部署说明与配置矩阵
├── docs/                   # 项目级设计文档
├── Makefile                # 快捷命令（委托 docker/）
└── README.md
```

---

## 部署方式

### 方式一：本地开发（推荐日常改代码）

**环境要求**：Python 3.10+、Node.js 18+、MongoDB、uv / npm。

**1. 后端**

```bash
cd diag_backend
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env
# 编辑 .env：MONGODB_URI、JWT_SECRET_KEY、OA_JWT_SECRET、OPENAI_API_KEY 等

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API 文档：http://localhost:8000/docs

**2. 前端**（另开终端）

```bash
cd diag_frontend
npm install
cp .env.example .env.local
# VITE_API_BASE_URL=http://localhost:8000

npm run dev
```

- 访问：http://localhost:3000

**代码改动如何生效**

| 改动 | 操作 |
|------|------|
| 后端 Python | `--reload` 下保存即热重载 |
| 前端 TS/组件 | `npm run dev` 下保存即热更新 |
| 前端 `VITE_*` 环境变量 | 修改后需重启 `npm run dev` |
| `configs/factories.yaml` | 保存后重启后端（或未使用 reload 时重启） |
| Python 依赖变更 | `uv pip install -r requirements.txt` 后重启后端 |

---

### 方式二：Docker Compose（内网一键起服务）

适合在同一台机器上固定跑 **MongoDB + 后端 + 前端**，无需本机单独安装 Python/Node（仍需能访问内网 MES、LLM 等外部地址）。

```bash
cd docker
cp .env.example .env
# 编辑 .env：JWT_SECRET_KEY、OA_JWT_SECRET、VITE_API_BASE_URL 等
# 从其他电脑访问前端时，VITE_API_BASE_URL 改为 http://<宿主机IP>:8000

docker compose up -d --build
```

| 服务 | 默认地址 |
|------|----------|
| 前端 | http://localhost:3000 |
| API / Swagger | http://localhost:8000/docs |

仓库根目录也可执行 `make up`（等价于在 `docker/` 下 compose）。

**代码改动如何生效**

| 改动 | 操作 |
|------|------|
| 后端代码 | `cd docker && docker compose up -d --build backend` |
| 前端代码 | `docker compose up -d --build frontend` |
| `diag_backend/configs/factories.yaml` | `docker compose restart backend`（已挂载，无需 rebuild） |
| `docker/.env` 中后端变量 | `docker compose up -d --force-recreate backend` |
| `VITE_API_BASE_URL` | 必须 `docker compose up -d --build frontend` |

更多说明：[docker/README.md](docker/README.md)、[deploy/README.md](deploy/README.md)。

---

### 方式三：生产环境（非容器）

典型做法：Nginx 反向代理 + 多 worker Uvicorn + 独立 MongoDB；前端 `npm run build` 后由 Nginx 托管静态资源。

- 后端：`uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4`（注意多 worker 会重复跑看板定时任务，见后端文档）
- 环境变量与 CORS、JWT、日志等见 [diag_backend/docs/deployment/production.md](diag_backend/docs/deployment/production.md)

---

## 环境变量

### 后端 `diag_backend/.env`

参考 [diag_backend/.env.example](diag_backend/.env.example)，常用项：

| 变量 | 说明 |
|------|------|
| `MONGODB_URI` | MongoDB 连接串 |
| `MONGODB_DB_NAME` | 数据库名 |
| `JWT_SECRET_KEY` | 生产环境务必使用长随机串 |
| `OA_JWT_SECRET` | Springboard OA payload 共享验签密钥 |
| `OPENAI_API_KEY` / `OPENAI_API_URL` | LLM（未配置时可走 mock） |
| `RAGFLOW_API_URL` / `RAGFLOW_API_KEY` | 知识库（可选） |

厂区 MES 地址在 `diag_backend/configs/factories.yaml` 中配置（`base_url`、`log_base_url` 等）。

### 前端 `diag_frontend/.env.local`

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_OA_LOGIN_URL=http://tl.cooacloud.com/springboard_v3/login_proxy/diagweaveeye
```

Docker 构建前端时，对应变量在 `docker/.env` 的 `VITE_API_BASE_URL`。

---

## API 概览

完整列表以 Swagger 为准：http://localhost:8000/docs

| 前缀 | 说明 |
|------|------|
| `/api/auth` | 注册、登录、当前用户 |
| `/api/diagnosis` | SN 诊断、异常日志剖析、历史记录 |
| `/api/error-logs` | 异常看板统计与趋势 |
| `/api/analytics` | 数据看板 insights |
| `/api/knowledge-base` | 知识库文档 |
| `/api/settings` | 全局 AI 配置 |
| `/api/sync/servers` | MES 实时查询（服务器/测试明细） |
| `/api/factories` | 厂区列表 |

---

## 开发

```bash
# 后端测试
cd diag_backend && pytest

# 前端类型检查
cd diag_frontend && npm run lint

# Python 格式化 / 检查
ruff format . && ruff check .
```

### 可选：文档站

```bash
# 项目级 docs/
cd docs && npm install && npm run docs:dev

# 后端 API 文档站
cd diag_backend/docs && npm install && npm run docs:dev
```

---

## 相关文档

| 文档 | 路径 |
|------|------|
| 后端说明 | [diag_backend/README.md](diag_backend/README.md) |
| 前端说明 | [diag_frontend/README.md](diag_frontend/README.md) |
| Docker 部署 | [docker/README.md](docker/README.md) |
| 部署配置矩阵 | [deploy/README.md](deploy/README.md) |
| 开发协作说明 | [CLAUDE.md](CLAUDE.md) |

---

## License

MIT License

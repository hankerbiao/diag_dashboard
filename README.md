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

WeaveEye 是一个前后端分离的智能诊断系统，提供设备 SN 深度诊断、异常日志分析、趋势数据统计等功能。系统结合知识图谱与 LLM（大语言模型）实现智能诊断推理。

### 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         WeaveEye 系统架构                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│   │    前端     │    │    后端     │    │   文档站    │        │
│   │  React 19   │◄──►│   FastAPI   │    │  VitePress  │        │
│   │  + Vite     │    │  + MongoDB  │    │             │        │
│   │  + Tailwind │    │  + OpenAI   │    │             │        │
│   └─────────────┘    └──────┬──────┘    └─────────────┘        │
│                             │                                    │
│                    ┌────────▼────────┐                          │
│                    │     MongoDB     │                          │
│                    │   10.17.154.252 │                          │
│                    └─────────────────┘                          │
│                             │                                    │
│                    ┌────────▼────────┐                          │
│                    │   LLM Services  │                          │
│                    │  OpenAI/Gemini  │                          │
│                    └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

### 核心功能

| 模块 | 功能 | 描述 |
|------|------|------|
| **SN 诊断** | 深度诊断 | 根据设备序列号查询设备信息、测试日志、维修历史 |
| **异常分析** | 日志分析 | 分析测试异常的根本原因并提供修复建议 |
| **数据看板** | 趋势统计 | 按厂区/时间范围统计直通率、问题类型分布 |
| **数据同步** | 外部对接 | 从三方 API 同步设备测试数据 |

### 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| **前端框架** | React 19 + TypeScript | 现代响应式 UI |
| **构建工具** | Vite 6 | 快速开发体验 |
| **样式方案** | Tailwind CSS 4 | 原子化 CSS |
| **图表库** | Recharts | 数据可视化 |
| **动画库** | Motion | 流畅交互动效 |
| **后端框架** | FastAPI | 高性能 Python Web |
| **异步驱动** | Motor | MongoDB 异步操作 |
| **LLM 集成** | OpenAI / Gemini | AI 推理能力 |
| **认证方案** | JWT | Token 认证 |

---

## 目录结构

```
diag_ai_analysis/
├── diag_backend/              # Python FastAPI 后端
│   ├── app/
│   │   ├── core/              # 核心模块 (配置/认证/数据库)
│   │   ├── routers/           # API 路由
│   │   ├── services/          # 业务服务 (LLM/知识图谱)
│   │   ├── models/            # Pydantic 数据模型
│   │   └── prompts/           # AI 提示词模板
│   ├── main.py                # 应用入口
│   ├── requirements.txt       # 生产依赖
│   └── README.md              # 后端详细文档
│
├── diag_frontend/             # React TypeScript 前端
│   ├── src/
│   │   ├── api/               # API 服务层
│   │   ├── components/        # React 组件
│   │   ├── contexts/          # React Context
│   │   ├── hooks/             # 自定义 Hooks
│   │   ├── data/              # 模拟数据
│   │   └── types/             # TypeScript 类型
│   ├── package.json
│   └── README.md              # 前端详细文档
│
├── docs/                      # VitePress 文档
│   ├── api/                   # API 文档
│   ├── database/              # 数据库设计
│   ├── deployment/            # 部署指南
│   └── design/                # 设计文档
│
├── docker/                    # docker compose up -d
├── deploy/                    # 部署与配置说明
├── Makefile                   # make up → docker/
├── CLAUDE.md                  # Claude Code 指导文件
└── README.md                  # 项目总览 (本文件)
```

---

## 快速开始

### 环境要求

- **运行时**: Python 3.10+ / Node.js 18+
- **数据库**: MongoDB Server
- **包管理**: uv (Python) / npm (Node.js)

### 1. 克隆项目

```bash
git clone <repository-url>
cd diag_ai_analysis
```

### 2. 后端启动

```bash
cd diag_backend

# 创建虚拟环境
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 安装依赖
uv pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填写实际配置

# 启动服务
uvicorn app.main:app --reload --port 8000
```

API 文档: http://localhost:8000/docs

### 3. 前端启动

```bash
cd diag_frontend

# 安装依赖
npm install

# 配置环境变量
cp .env.example .env.local
# 编辑 .env.local 填写实际配置

# 启动开发服务器
npm run dev
```

访问地址: http://localhost:3000

### 4. Docker Compose（内网一键部署）

```bash
cd docker
cp .env.example .env
# 编辑 .env 后
docker compose up -d --build
```

| 服务 | 默认地址 |
|------|----------|
| 前端 | http://localhost:3000 |
| API | http://localhost:8000 |

详见 [docker/README.md](docker/README.md)、[deploy/README.md](deploy/README.md)。

### 5. 文档站 (可选)

```bash
cd docs
npm install
npm run docs:dev
```

---

## 环境变量配置

### 后端 (.env)

```env
# MongoDB
MONGODB_URI=mongodb://10.17.154.252:27018
MONGODB_DB_NAME=diag_analysis

# JWT 认证
JWT_SECRET_KEY=your-64-character-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# AI 服务
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# 服务器
HOST=0.0.0.0
PORT=8000
```

### 前端 (.env.local)

```env
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=xxx
VITE_API_BASE_URL=http://localhost:8000
```

---

## API 端点总览

### 认证模块 (`/api/auth`)

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/auth/register` | 用户注册 |
| POST | `/auth/login` | 用户登录 |

### 诊断模块 (`/api/diagnosis`)

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/diagnosis/sn` | SN 深度诊断 |
| POST | `/diagnosis/error-log/{id}` | 异常日志分析 |

### 异常日志 (`/api/error-logs`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/error-logs/stats` | 统计数据 |
| GET | `/error-logs/trend` | 趋势数据 |
| GET | `/error-logs/stats/yield` | 直通率趋势 |

### 数据同步 (`/api/sync`)

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/sync/trigger` | 触发同步 |
| GET | `/sync/status` | 同步状态 |
| GET | `/sync/jobs` | 任务列表 |

---

## 开发指南

### 代码规范

- **Python**: 使用 ruff 进行代码检查
- **TypeScript**: 使用 ESLint + TypeScript 类型检查
- **提交规范**: 遵循 Conventional Commits

### 测试

```bash
# 后端测试
cd diag_backend
pytest

# 前端类型检查
cd diag_frontend
npm run lint
```

---

## 相关资源

- [后端详细文档](./diag_backend/README.md)
- [前端详细文档](./diag_frontend/README.md)
- [API 文档](./docs/api/)
- [数据库设计](./docs/database/)
- [部署指南](./docs/deployment/)

---

## License

MIT License
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**WeaveEye** - 智能诊断系统前后端分离应用

- **前端**: React 19 + TypeScript + Vite (当前目录 `diag_frontend/`)
- **后端**: FastAPI + Supabase (`diag_backend/`)

## Development Commands

### Frontend (diag_frontend)
```bash
npm install              # 安装依赖
npm run dev              # 开发服务器 (端口 3000)
npm run lint             # 类型检查
npm run build            # 构建生产版本
```

### Backend (diag_backend)
```bash
cd diag_backend
uv pip install -r requirements.txt   # 安装依赖
uvicorn app.main:app --reload        # 开发服务器 (端口 8000)
```

## Architecture

### 前端目录结构
```
src/
├── api/                   # API 服务层
│   ├── supabase.ts        # Supabase 客户端 (数据查询)
│   ├── fastapi.ts         # FastAPI 客户端 (AI 诊断)
│   └── index.ts
├── components/
│   ├── layout/            # 布局组件
│   ├── diagnosis/         # 单机诊断模块
│   ├── dashboard/         # 数据看板模块
│   ├── error-logs/        # 异常看板模块
│   └── settings/          # 设置模块
├── data/mockData.ts       # 模拟数据
├── types/index.ts         # 类型定义
├── App.tsx                # 根组件
└── main.tsx               # 入口
```

### 后端目录结构 (diag_backend)
```
app/
├── main.py                # FastAPI 应用入口
├── core/                  # 核心模块
│   ├── config.py          # 配置管理
│   ├── supabase.py        # Supabase 客户端
│   └── security.py        # JWT 认证
├── routers/               # API 路由
│   ├── diagnosis.py       # 诊断相关 API
│   ├── error_logs.py      # 异常日志 API
│   └── settings.py        # 设置 API
├── services/              # 业务服务
│   ├── llm_service.py     # LLM 调用封装
│   └── knowledge_graph.py # 知识图谱检索
└── models/                # Pydantic 模型
    ├── request.py
    └── response.py
```

### 技术栈分工

| 功能 | 技术 |
|------|------|
| 数据存储 | Supabase PostgreSQL |
| 实时订阅 | Supabase Realtime |
| 认证授权 | Supabase Auth + RLS |
| CRUD 操作 | Supabase 直接访问 |
| AI 推理 | FastAPI + OpenAI/Gemini |
| API 网关 | FastAPI |

### API 通信流程
```
前端 ──────▶ Supabase (数据查询)
      │
      └─────▶ FastAPI (AI 诊断) ──▶ LLM API
```

## Key Files

### 前端 API 层
- `src/api/supabase.ts` - Supabase 直接查询 (异常日志、统计数据)
- `src/api/fastapi.ts` - FastAPI 调用 (AI 诊断、设置管理)

### 前端类型
- `src/types/index.ts` - 共享类型定义
- `src/vite-env.d.ts` - Vite 环境变量类型

### 后端配置
- `.env.example` - 环境变量模板

## Environment Variables

### Frontend (.env.local)
```bash
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=xxx
VITE_API_BASE_URL=http://localhost:8000
```

### Backend (.env)
```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_KEY=xxx
OPENAI_API_KEY=sk-xxx
```
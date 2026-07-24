# WeaveEye 智能诊断系统后端

## 项目概览

| 属性 | 说明 |
|------|------|
| **项目名称** | WeaveEye Backend |
| **项目类型** | Python FastAPI RESTful API |
| **技术栈** | Python 3.10+ / FastAPI / MongoDB (Motor) / OpenAI |
| **认证方式** | OA SSO + 应用 Bearer JWT |
| **数据库** | MongoDB (`10.17.154.252:27018`) |

## 核心功能模块

### 1. 诊断系统 (`/api/diagnosis`)
- **SN 深度诊断**: 根据设备序列号查询设备信息、测试日志、维修历史，结合知识图谱和 LLM 进行智能诊断
- **异常日志分析**: 分析测试异常的根本原因并提供修复建议

### 2. 异常日志统计 (`/api/error-logs`)
- 趋势数据统计（按厂区/时间范围）
- 直通率分析
- 问题类型分布
- 线体拦截数统计

### 3. 数据同步服务 (`/api/sync`)
- 从三方 API 同步设备测试数据
- 支持并发请求、重试机制
- 任务管理和状态跟踪

### 4. 用户认证 (`/api/auth`)
- OA 单点登录回调
- 应用 Bearer JWT 认证
- 用户设置管理 (`/api/settings`)

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Application                  │
├─────────────────────────────────────────────────────────┤
│  Routers                                                 │
│  ├─ auth.py       │ 认证 (OA callback/JWT)             │
│  ├─ diagnosis.py  │ 诊断 (SN诊断/异常分析)              │
│  ├─ error_logs.py │ 异常日志统计                        │
│  ├─ settings.py   │ 用户设置                            │
│  └─ sync.py       │ 数据同步                            │
├─────────────────────────────────────────────────────────┤
│  Services                                                │
│  ├─ llm_service.py       │ LLM 调用 (OpenAI/Gemini)     │
│  ├─ knowledge_graph.py   │ 知识图谱                      │
│  └─ sync_service.py      │ 同步服务                      │
├─────────────────────────────────────────────────────────┤
│  Core                                                    │
│  ├─ config.py    │ 配置管理 (Pydantic Settings)         │
│  ├─ auth.py      │ 应用 Bearer JWT                      │
│  └─ mongodb.py   │ MongoDB 异步连接 (Motor)             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │   MongoDB    │
                   │ 10.17.154.   │
                   │   252:27018  │
                   └──────────────┘
```

## 目录结构

```
app/
├── main.py                    # FastAPI 应用入口，生命周期管理
├── core/                      # 核心模块
│   ├── config.py              # 配置管理（Pydantic Settings）
│   ├── auth.py                # 应用 Bearer JWT
│   └── mongodb.py             # MongoDB 异步连接（Motor）
├── routers/                   # API 路由
│   ├── auth.py                # 认证接口
│   ├── diagnosis.py           # 诊断接口
│   ├── error_logs.py          # 异常日志接口
│   ├── settings.py            # 用户设置接口
│   └── sync.py                # 数据同步接口
├── services/                  # 业务服务层
│   ├── llm_service.py         # LLM 调用（OpenAI/Gemini）
│   ├── knowledge_graph.py     # 知识图谱
│   └── sync_service.py        # 同步服务
├── models/                    # Pydantic 数据模型
│   ├── request.py             # 请求模型
│   ├── response.py            # 响应模型
│   └── auth.py                # 认证模型
└── prompts/                   # AI 提示词模板
```

## 快速开始

### 环境要求
- Python 3.10+
- MongoDB Server
- uv (推荐) 或 pip

### 安装步骤

```bash
# 1. 创建虚拟环境
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 2. 安装依赖
uv pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填写实际配置
```

### 配置说明 (.env)

```env
# MongoDB
MONGODB_URI=mongodb://10.17.154.252:27018
MONGODB_DB_NAME=diag_analysis

# JWT 认证
JWT_SECRET_KEY=your-64-character-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
OA_JWT_SECRET=replace-with-springboard-shared-secret

# AI 服务
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# 服务器
HOST=0.0.0.0
PORT=8000
DEBUG=true

# 数据同步
SYNC_API_BASE_URL=http://10.2.68.103
SYNC_MAX_CONCURRENCY=5
SYNC_MAX_RETRIES=3
```

### 运行

```bash
# 开发模式
uvicorn app.main:app --reload --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### API 文档

启动服务后访问: **http://localhost:8000/docs** (Swagger UI)

## API 端点

### 认证 (`/api/auth`)
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/oa/callback` | 验证 OA payload 并签发应用 JWT |
| GET | `/auth/me` | 获取当前 OA 用户 |

### 诊断 (`/api/diagnosis`)
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/diagnosis/sn` | SN 深度诊断 |
| POST | `/diagnosis/error-log/{id}` | 异常日志分析 |

### 异常日志 (`/api/error-logs`)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/error-logs/stats` | 获取统计数据 |
| GET | `/error-logs/trend` | 趋势数据 |
| GET | `/error-logs/stats/yield` | 直通率趋势 |

### 设置 (`/api/settings`)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/settings` | 获取用户设置 |
| PUT | `/settings` | 更新用户设置 |

### 同步 (`/api/sync`)
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/sync/trigger` | 触发同步任务 |
| GET | `/sync/status` | 获取同步状态 |
| GET | `/sync/jobs` | 同步任务列表 |

## 依赖说明

| 依赖 | 用途 |
|------|------|
| `fastapi>=0.109.0` | Web 框架 |
| `uvicorn[standard]>=0.27.0` | ASGI 服务器 |
| `motor>=3.6.0` | 异步 MongoDB 驱动 |
| `pymongo>=4.9.0` | MongoDB 同步驱动 |
| `openai>=1.10.0` | LLM API 调用 |
| `python-jose[cryptography]>=3.3.0` | JWT 认证 |
| `pydantic>=2.5.0` | 数据验证 |
| `pydantic-settings>=2.1.0` | 配置管理 |
| `python-dotenv>=1.0.0` | 环境变量加载 |
| `httpx>=0.26.0` | HTTP 客户端 |

## 开发

### 代码规范
- 使用 `ruff` 进行代码检查
- 使用 `black` 进行代码格式化
- 所有函数使用类型注解

### 测试
```bash
# 运行测试
pytest

# 带覆盖率
pytest --cov=app --cov-report=term-missing
```

# 项目结构

```
diag_ai_analysis/
├── diag_backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口，lifespan 管理 MongoDB 连接 + 调度器
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings（MongoDB/JWT/AI/RAGFlow/Sync）
│   │   │   ├── auth.py              # 应用 Bearer JWT 签发/验证
│   │   │   ├── mongodb.py           # Motor 异步连接管理
│   │   │   ├── mongodb_indexes.py   # 启动时自动创建索引 + seed 默认厂区
│   │   │   └── factory_config.py    # 读取 configs/factories.yaml
│   │   ├── routers/                 # API 路由层
│   │   │   ├── auth.py              # OA callback 与 GET /me
│   │   │   ├── diagnosis.py         # POST /sn, /error-log/{id}/analyze（SSE）
│   │   │   ├── error_logs.py        # GET /stats, /trend
│   │   │   ├── analytics.py         # GET /insights（看板聚合数据）
│   │   │   ├── factories.py         # GET /factories
│   │   │   ├── knowledge_base.py    # CRUD 知识库文档
│   │   │   ├── settings.py          # GET/PUT /settings
│   │   │   └── sync.py              # GET /servers, /jobs（只读查询）
│   │   ├── services/                # 业务逻辑层
│   │   │   ├── llm_service.py       # OpenAI/Gemini 封装（含 mock 模式）
│   │   │   ├── ragflow_service.py   # RAGFlow API 封装
│   │   │   ├── knowledge_graph.py   # 知识图谱检索
│   │   │   ├── analytics_service.py # 看板预计算 + 每小时调度
│   │   │   └── sync_service.py      # 数据同步（三方 MES API → MongoDB）
│   │   ├── models/                  # Pydantic 请求/响应模型
│   │   └── prompts/                 # AI 提示词模板
│   ├── configs/
│   │   └── factories.yaml           # 厂区配置（单一数据源）
│   └── tests/                       # pytest 测试
│
├── diag_frontend/                   # React 前端
│   ├── src/
│   │   ├── api/
│   │   │   ├── auth.ts              # OA 回调与应用 JWT 管理
│   │   │   ├── fastapi.ts           # 通用 HTTP 客户端 + 各模块 API
│   │   │   └── index.ts
│   │   ├── components/
│   │   │   ├── auth/                # LoginPage, AuthGuard
│   │   │   ├── layout/              # Sidebar, Header
│   │   │   ├── common/              # LoadingSpinner, ThemeToggle
│   │   │   ├── diagnosis/           # 单机诊断
│   │   │   ├── dashboard/           # 数据看板（6 种图表）
│   │   │   ├── error-logs/          # 异常看板 + 诊断弹窗
│   │   │   ├── knowledge-base/      # 知识库管理
│   │   │   └── settings/            # 设置页
│   │   ├── contexts/
│   │   │   ├── AuthContext.tsx       # 认证状态管理
│   │   │   └── ThemeContext.tsx      # 主题切换
│   │   ├── hooks/                   # useChartTheme, useDebounce
│   │   ├── types/                   # 共享 TS 类型
│   │   └── utils/                   # 工具函数
│   └── package.json
│
├── docs/                            # VitePress 文档
│   ├── .vitepress/config.mts
│   ├── guide/                       # 使用指南
│   ├── architecture/                # 架构文档
│   ├── workflows/                   # 业务工作流
│   ├── api/                         # API 参考
│   ├── database/                    # 数据库
│   ├── deployment/                  # 部署
│   └── operations/                  # 运维
│
├── scripts/                         # 独立工具脚本
│   ├── sync_data.py                 # 厂区数据同步
│   └── sync_mes.py                  # MES 维修记录同步 + RAGFlow 上传
│
└── configs/
    └── factories.yaml               # 厂区配置（共享）
```

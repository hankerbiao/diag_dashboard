---
layout: home

hero:
  name: "WeaveEye Backend"
  text: "FastAPI 后端开发文档"
  tagline: "Motor 异步 MongoDB · JWT 认证 · MES/SIMS 集成 · LLM + RAGFlow 诊断管道 · 看板预计算"
  actions:
    - theme: brand
      text: 快速入门
      link: /guide/getting-started
    - theme: alt
      text: 架构概览
      link: /architecture/overview
    - theme: alt
      text: 诊断工作流
      link: /workflows/sn-diagnosis

features:
  - title: 全链路 async/await
    details: FastAPI + Motor + httpx.AsyncClient，路由、数据库、外部 MES/RAGFlow/LLM 调用均为异步，无阻塞 I/O。
  - title: 分层清晰
    details: routers → services → core/mongodb，Pydantic 模型统一请求/响应，业务逻辑集中在 services。
  - title: 多厂区 MES 集成
    details: configs/factories.yaml 单一数据源，MESDirectService 实时查 SIMS，sync_scheduler 调度 scripts/ 同步脚本。
  - title: 三阶段 AI 诊断
    details: 日志下载 → RAGFlow 知识检索 → LLM 推理；SSE 流式推送进度，diagnosis_cache 缓存结果。
  - title: 看板预计算
    details: AnalyticsService 每小时 refresh_all，MongoDB aggregation + analytics_snapshots 快照缓存。
  - title: 可观测性
    details: 结构化日志、请求中间件、sync_jobs 进度追踪、全局异常处理器。
---

## 文档说明

本文档站位于 `diag_backend/docs/`，专门描述 **WeaveEye 后端 API** 的实现细节，面向：

- 新加入的后端/全栈开发者
- 需要扩展路由、服务或 MongoDB 索引的维护者
- 排查 MES 502、日志下载失败、聚合 QueryPlanKilled 等生产问题的运维人员

项目根目录另有全栈文档站（`docs/`），覆盖前后端与部署；**本站点聚焦后端代码与运行机制**。

## 常用命令

```bash
# 后端开发
cd diag_backend
uv pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 测试
pytest
pytest --cov=app --cov-report=term-missing

# 本文档站
cd diag_backend/docs
npm install
npm run docs:dev    # http://localhost:5173
npm run docs:build
```

## 技术栈速查

| 组件 | 选型 | 说明 |
|------|------|------|
| Web 框架 | FastAPI 0.109+ | OpenAPI 自动生成，`/docs` Swagger UI |
| ASGI 服务器 | Uvicorn | `--reload` 开发热重载 |
| 数据库 | MongoDB + Motor 3.6+ | 异步驱动，库名默认 `diag_analysis` |
| 认证 | OA SSO + python-jose | OA payload 验签 + 应用 JWT Bearer |
| AI | OpenAI 兼容 API | 支持自定义 base_url / Gemini |
| 知识库 | RAGFlow（可选） | 未配置时不影响启动 |
| 配置 | pydantic-settings + `.env` | 厂区 YAML 与 `.env` 分离 |

## 源码入口

| 文件 | 职责 |
|------|------|
| `app/main.py` | FastAPI 实例、CORS、全局异常、路由注册 |
| `app/core/lifespan.py` | 启动：MongoDB → 分析调度 → 同步调度 |
| `app/core/mongodb.py` | 连接池、`ensure_indexes`、seed |
| `configs/factories.yaml` | 厂区 MES/日志地址（与 scripts 共享） |

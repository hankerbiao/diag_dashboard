# 分层设计

## Router 层

文件：`app/routers/*.py`

职责：

- 声明 `APIRouter(prefix=..., tags=[...])`
- `Depends(get_current_user)` 保护需登录接口
- 解析 Query/Body/Path，调用 service 或内联 orchestration（诊断路由较厚）
- 返回 Pydantic model 或 `StreamingResponse`（SSE）

**诊断路由**（`diagnosis.py`）因 SSE 与多阶段管道，编排逻辑较长，但仍将 LLM/RAG/MES 委托给 services。

## Service 层

文件：`app/services/*.py`

| 服务 | 类型 |
|------|------|
| `LLMService` | 类实例 `llm_service` |
| `KnowledgeGraphService` | 类实例 `knowledge_graph` |
| `AnalyticsService` | 单例 + 后台 task |
| `SyncSchedulerService` | 单例 + 后台 task |
| `SyncService` | 查询 sync 集合 |
| `MESDirectService` | 上下文管理器 `async with` |
| `ragflow_service` | 函数式模块 |
| `ErrorLogsService` | 单例 |

Service **不**导入 FastAPI 类型，便于单元测试。

## Core 层

| 模块 | 作用 |
|------|------|
| `config` | 环境变量 |
| `mongodb` | 连接生命周期 |
| `mongodb_indexes` | 索引 + seed |
| `auth` | OA callback、应用 JWT、`get_current_user` |
| `factory_config` | YAML 厂区 |
| `lifespan` | FastAPI lifespan |
| `logger` | 根日志配置 |
| `utils` | 纯函数工具 |

## Model 层

`app/models/`：

- `auth.py` — 登录注册
- `api.py` — `ApiResponse` 泛型包装
- `diagnosis.py` — 诊断响应结构
- `knowledge.py` — 知识库
- `request.py` — 通用请求体

请求体 snake_case；前端部分字段 camelCase 由前端 adapter 处理。

## Middleware

`app/middleware/logging.py` — 记录请求方法、路径、耗时。

## 依赖方向

```
routers → services → core
routers → models
services → core
services → models (少量)
core ↛ services  (禁止反向)
```

## 扩展点

| 需求 | 推荐位置 |
|------|----------|
| 新 REST 资源 | `routers/` + `services/` |
| 新集合索引 | `mongodb_indexes.py` |
| 新厂区字段 | `factories.yaml` + `factory_config.py` |
| 新 LLM 提示 | `app/prompts/` + `llm_service.py` |
| 定时任务 | 参考 `AnalyticsService._loop` 或 `SyncSchedulerService` |

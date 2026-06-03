# 项目结构

```
diag_backend/
├── app/                          # Python 应用包
│   ├── main.py                   # FastAPI 入口
│   ├── core/                     # 基础设施
│   │   ├── config.py             # pydantic-settings
│   │   ├── auth.py               # JWT / 密码哈希
│   │   ├── mongodb.py            # Motor 连接
│   │   ├── mongodb_indexes.py    # 启动索引 + seed
│   │   ├── factory_config.py     # factories.yaml 读取
│   │   ├── lifespan.py           # startup/shutdown
│   │   ├── logger.py             # 日志配置
│   │   └── utils.py              # 时间、日志 URL、ObjectId 等
│   ├── routers/                  # HTTP 路由（薄层）
│   ├── services/                 # 业务逻辑
│   ├── models/                   # Pydantic 请求/响应模型
│   ├── middleware/               # 请求日志中间件
│   └── prompts/                  # LLM 提示词模板
├── configs/
│   └── factories.yaml            # 厂区 MES/日志配置
├── tests/                        # pytest
├── migrations/
│   └── init_mongodb.py           # 历史初始化脚本（索引已由 ensure_indexes 接管）
├── data/                         # 本地知识库文件、维修记录等
├── docs/                         # 本文档站 (VitePress)
├── requirements.txt
├── download_ftp.py               # FTP 下载参考实现
└── main.py                       # 可选启动包装
```

## 分层约定

| 层 | 职责 | 禁止 |
|----|------|------|
| **routers** | 参数校验、鉴权、调用 service、组装 `ApiResponse` | 复杂聚合、直接写多集合事务 |
| **services** | 业务规则、外部 API、聚合管道、缓存策略 | 直接依赖 `Request` 对象 |
| **core** | 连接、配置、横切能力 | 业务语义 |
| **models** | API 契约（camelCase 由前端约定，后端多用 snake_case） | 数据库 ORM（无 ORM） |

## 路由注册

`app/main.py` 统一前缀 `/api`：

```python
app.include_router(auth.router, prefix="/api")
app.include_router(diagnosis.router, prefix="/api")
# ...
```

各 router 自带二级 prefix，例如 `/api/diagnosis/sn`。

## 单例服务

以下通过模块级 getter 懒加载单例：

- `get_analytics_service()`
- `get_sync_scheduler_service()`
- `get_sync_service()`
- `get_error_logs_service()`
- `llm_service`（模块实例）
- `knowledge_graph`（模块实例）

## 与 scripts/ 的关系

| 组件 | 后端 | scripts/ |
|------|------|----------|
| 厂区配置 | `factory_config.py` | `sync_data.py` 读同一 YAML |
| SIMS 同步 | `SyncSchedulerService` 调 subprocess | `scripts/sync_data.py` |
| MES 维修同步 | 调 `scripts/sync_mes.py` | 独立脚本 |

后端**不内嵌**同步逻辑，通过子进程调用脚本，stdout 写入 `sync_jobs.progress`。

## 数据目录

- `data/knowledge_base/` — 知识库上传文件的本地副本（`KNOWLEDGE_BASE_STORAGE_PATH`）
- `data/maintenance_records/` — 维修记录文本（知识图谱检索用）
- `logs/` — 若配置 `LOG_FILE` 则写入

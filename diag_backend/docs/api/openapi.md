# OpenAPI / Swagger

FastAPI 自动生成 OpenAPI 3.0 schema。

## 访问

服务启动后：

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **JSON:** `http://localhost:8000/openapi.json`

## 认证测试

1. `POST /api/auth/login` 获取 token
2. Swagger 右上角 **Authorize**
3. 输入 `Bearer <token>`（或仅 token，视 UI 版本）

## 标签分组

与 `routers/*.py` 中 `tags=[...]` 一致：认证、诊断、异常日志、数据分析、数据同步、知识库、设置、厂区管理。

## 导出

```bash
curl http://localhost:8000/openapi.json -o openapi.json
```

## 与本文档站关系

- **OpenAPI** — 机器可读、Try it out、精确 schema
- **本 VitePress** — 架构、工作流、运维、设计决策

两者互补，开发时建议同时保留。

## 模型定义

Pydantic v2 模型在 `app/models/`，Swagger 中显示 JSON Schema。

复杂诊断响应见 `app/models/diagnosis.py`。

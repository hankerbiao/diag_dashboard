# 本地开发流程

## 日常循环

1. 修改代码 → Uvicorn `--reload` 自动重载
2. `ruff check .` / `ruff format .`（若项目启用）
3. `pytest` 相关模块
4. Swagger `http://localhost:8000/docs` 手测

## 添加新 API 端点

1. 在 `app/models/` 定义请求/响应模型
2. 在 `app/services/` 实现业务（如需）
3. 在 `app/routers/` 添加路由，使用 `Depends(get_current_user)` 若需登录
4. 在 `tests/test_*_routes.py` 补充测试
5. 更新本文档站 `routers/` 章节

## 添加 MongoDB 集合/索引

1. 在 `mongodb_indexes.py` 的 `ensure_indexes()` 添加 `create_index`（幂等）
2. 在 `database/collections.md` 文档化字段
3. **不要**每次启动无条件 `drop_index`（会导致 QueryPlanKilled）

## 修改厂区

1. 编辑 `configs/factories.yaml`
2. 重启后端（或依赖下次 seed 仅对新 factory_id upsert `factory_sites`）
3. 前端 Header 厂区下拉自动读取 `GET /api/factories`

## 调试 MES/SIMS

- 打开 `LOG_LEVEL=DEBUG`
- 查看 `MESDirectService._request_debug` 输出（诊断路由 SIMS 失败时会 log）
- 用 curl 直连厂区 `base_url` 对比网络

## 调试 LLM

- 未配置 `OPENAI_API_KEY` 时 `LLMService` 可走 mock 返回
- 生产配置在 MongoDB `global_app_config`（`_id: ai_config`），Settings API 可覆盖

## 热重载注意事项

`uvicorn --reload` 会短暂存在**两个进程**：

- 新进程 `ensure_indexes` 若 drop 索引，旧进程聚合可能报 **175 QueryPlanKilled**
- 已修复：仅 legacy unique 索引才 drop；聚合带重试

## 代码风格

- 全异步：数据库用 `await`，HTTP 用 `httpx.AsyncClient`
- ObjectId 对外统一转 `str` 字段名 `id`
- 时间戳 ISO 8601 UTC（`utc_now_iso()`）
- 日志用 `logging.getLogger(__name__)`，避免 print

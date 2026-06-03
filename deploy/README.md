# WeaveEye Docker 部署

内网一键启动：**MongoDB + 后端 + 前端**（方案 A：浏览器访问 `http://<host>:3000`，API `http://<host>:8000`）。

MES / RAGFlow 仍通过配置文件指向现有内网服务，不包含在 Compose 中。

## 快速开始

```bash
cd docker
cp .env.example .env
# 编辑 .env：至少修改 JWT_SECRET_KEY；若从其他机器访问，改 VITE_API_BASE_URL 为 http://<宿主机IP>:8000

docker compose up -d --build
# 或在仓库根目录: make up
```

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| API / Swagger | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |

首次启动后在后端日志中确认 `MongoDB indexes ensured`；在 UI 注册账号即可使用（注册未关闭）。

## 配置矩阵

| 变量 / 文件 | 必填 | 说明 | Docker 处理 |
|-------------|------|------|-------------|
| `JWT_SECRET_KEY` | 是 | 签发 JWT | `.env` |
| `MONGODB_URI` | — | Compose 内由 compose 设为 `mongodb://mongo:27017` | 自动 |
| `MONGODB_DB_NAME` | 否 | 库名 | `.env` |
| `VITE_API_BASE_URL` | 是 | **构建前端时**写入静态资源 | `.env` → compose `build.args` |
| `diag_backend/configs/factories.yaml` | MES 功能需要 | 各厂区 `base_url` / `log_base_url` | **只读挂载**，改完 `docker compose restart backend` |
| `RAGFLOW_API_*` | 否 | 知识库 RAG | `.env` |
| `OPENAI_*` / `GEMINI_*` | 否 | LLM；无 key 可 mock | `.env` |
| `KNOWLEDGE_BASE_STORAGE_PATH` | — | 上传文件目录 | 卷 `knowledge_data` → `/data/knowledge_base` |
| `LOG_FILE` | 否 | 留空则 **stdout**（推荐） | compose 设 `LOG_FILE=` |

## 改代码后如何更新

| 变更 | 命令 |
|------|------|
| 后端 Python | `make restart-backend` 或 `docker compose up -d --build backend` |
| 前端 | `make restart-frontend`（会按 `.env` 中 `VITE_API_BASE_URL` 重新 build） |
| 仅 `factories.yaml` | `docker compose restart backend` |
| 仅 `.env`（后端） | `docker compose up -d --force-recreate backend` |
| 仅 `.env` 中 `VITE_API_BASE_URL` | 必须 **rebuild frontend** |

## 数据持久化

- `mongo_data`：MongoDB 数据
- `knowledge_data`：知识库上传文件

`docker compose down` 不删卷；`docker compose down -v` 会清空数据。

## 内网 MES / RAGFlow

Compose 主机需能访问 `factories.yaml` 与 `.env` 中的地址。在容器内自测：

```bash
docker compose exec backend curl -sS -o /dev/null -w "%{http_code}\n" http://<mes-host>/
```

## 架构说明

- 后端 **单 worker**，避免重复跑分析/同步调度器。
- **数据同步**不在容器内执行；请在宿主机或定时任务运行 `scripts/weaveeye_sync.py run`（见 `scripts/README.md`）。
- 日志输出到 `docker compose logs -f backend`。

## 故障排查

| 现象 | 处理 |
|------|------|
| 前端能开但登录失败 | 检查 `VITE_API_BASE_URL` 是否从浏览器可达（跨机用宿主机 IP） |
| backend 起不来 | `docker compose logs backend`；确认 mongo healthy |
| 同步失败 | 内网 MES 是否通；`docker compose exec backend ls /app/scripts` |

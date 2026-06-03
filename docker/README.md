# Docker 部署

在**本目录**启动 WeaveEye（MongoDB + 后端 + 前端）。

```bash
cd docker
cp .env.example .env
# 编辑 .env（JWT_SECRET_KEY、VITE_API_BASE_URL 等）

docker compose up -d --build
# 或: make up
```

| 服务 | 默认地址 |
|------|----------|
| 前端 | http://localhost:3000 |
| API | http://localhost:8000/docs |

- 构建上下文为上级仓库根目录；`.dockerignore` 在仓库根。
- 数据同步不在容器内执行，见 `../scripts/README.md`。
- 更完整的配置说明见 `../deploy/README.md`。

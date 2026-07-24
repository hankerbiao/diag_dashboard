# 快速入门

本文档假设你已在 macOS/Linux 上安装 **Python 3.11+**、**MongoDB**（或可访问远程实例）、**Node.js 18+**（仅文档站需要）。

## 1. 克隆与目录

```bash
git clone <repo-url> diag_ai_analysis
cd diag_ai_analysis/diag_backend
```

后端代码根目录为 `diag_backend/`，Python 包入口为 `app/`。

## 2. 创建虚拟环境并安装依赖

推荐使用 [uv](https://github.com/astral-sh/uv) 或 venv：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

核心依赖见 `requirements.txt`：`fastapi`、`motor`、`openai`、`python-jose`、`httpx`、`PyYAML` 等。

## 3. 环境变量

在 `diag_backend/` 下创建 `.env`（**勿提交 Git**）：

```env
MONGODB_URI=mongodb://10.17.154.252:27018
MONGODB_DB_NAME=diag_analysis
JWT_SECRET_KEY=your-random-64-char-secret
OA_JWT_SECRET=your-springboard-shared-secret
OPENAI_API_KEY=sk-...
OPENAI_API_URL=https://api.openai.com/v1
AI_MODEL=gpt-4-turbo
HOST=0.0.0.0
PORT=8000
DEBUG=true
```

完整变量说明见 [环境变量](/deployment/environment-vars)。

## 4. 厂区配置

编辑 `configs/factories.yaml`。后端 `factory_config.py` 与 `scripts/sync_data.py` **共用此文件**。

## 5. 启动服务

```bash
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/health
open http://localhost:8000/docs
```

## 6. 启动时序

1. MongoDB 连接 + 索引 + seed
2. 分析看板调度器启动
3. 数据同步调度器启动

详见 [应用生命周期](/architecture/lifecycle)。

## 7. 登录

打开前端后，未登录用户会自动跳转 OA Springboard。OA 回调由前端提交到
`POST /api/auth/oa/callback`，本项目不提供本地注册或密码登录。

## 8. 测试与文档站

```bash
pytest -q
cd docs && npm install && npm run docs:dev
```

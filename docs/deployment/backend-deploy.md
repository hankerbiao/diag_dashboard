# 后端部署

## 环境要求

- Python 3.10+
- MongoDB（目标服务器 `10.17.154.252:27018`）
- 可选：RAGFlow、OpenAI/Gemini 兼容 API

## 部署步骤

```bash
cd diag_backend

# 1. 安装依赖
uv pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env：设置 MONGODB_URI、JWT_SECRET_KEY 等

# 3. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 生产部署建议

### 进程管理

使用 Supervisor 或 systemd 管理进程：

```ini
# /etc/supervisor/conf.d/weaveeye-backend.conf
[program:weaveeye-backend]
command=/path/to/uvicorn app.main:app --host 0.0.0.0 --port 8000
directory=/path/to/diag_backend
user=www-data
autostart=true
autorestart=true
environment=PATH="/path/to/venv/bin"
```

### CORS 配置

生产环境需配置允许的前端域名：

```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 健康检查

```bash
curl http://localhost:8000/api/health
```

# 快速入门

## 环境要求

- Python 3.10+
- Node.js 18+
- MongoDB（目标服务器 `10.17.154.252:27018`）
- RAGFlow（可选，知识库功能需要）
- OpenAI / Gemini 兼容 API（可选，AI 诊断需要）

## 后端启动

```bash
cd diag_backend

# 安装依赖
uv pip install -r requirements.txt

# 配置环境变量（修改 .env 中的 MongoDB URI / JWT 密钥 / AI API Key 等）
cp .env.example .env

# 启动开发服务器
uvicorn app.main:app --reload --port 8000
```

后端启动后会自动连接 MongoDB，创建索引并 seed 默认厂区数据。  
API 文档地址：`http://localhost:8000/docs`

## 前端启动

```bash
cd diag_frontend

# 安装依赖
npm install

# 配置 API 地址（可选，默认 http://localhost:8000）
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local

# 启动开发服务器
npm run dev
```

前端开发服务器运行在 `http://localhost:3000`。

## 默认登录

系统启动后，通过前端注册第一个用户即成为管理员。  
认证流程详见[认证流程](/workflows/authentication)。

## 数据同步

首次使用需要从厂区 MES 同步测试数据：

```bash
cd scripts
pip install -r requirements.txt

# 同步最近 24 小时数据
python sync_data.py

# 同步指定厂区
python sync_data.py --factory kunshan
```

详见[数据同步脚本](/operations/data-sync-scripts)。

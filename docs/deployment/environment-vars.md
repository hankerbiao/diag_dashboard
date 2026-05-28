# 环境变量参考

所有环境变量在 `diag_backend/.env` 中配置，由 `app/core/config.py` 的 `Settings` 类管理。

## MongoDB

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `MONGODB_URI` | string | `mongodb://10.17.154.252:27018` | MongoDB 连接串 |
| `MONGODB_DB_NAME` | string | `diag_ai` | 数据库名 |
| `MONGODB_MAX_POOL_SIZE` | int | `100` | 连接池大小 |

## JWT 认证

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `JWT_SECRET_KEY` | string | — | JWT 签名密钥（必填） |
| `JWT_ALGORITHM` | string | `HS256` | 签名算法 |
| `JWT_EXPIRATION_MINUTES` | int | `60` | Token 过期时间（分） |
| `JWT_REMEMBER_DAYS` | int | `1` | "记住我" 过期天数 |

## AI / LLM

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `OPENAI_API_KEY` | string | — | LLM API Key（留空则 mock 模式） |
| `OPENAI_API_URL` | string | — | LLM API 地址（兼容 OpenAI 格式） |
| `AI_MODEL` | string | `gemini-2.5-flash` | 模型名 |
| `AI_TEMPERATURE` | float | `0.3` | 温度参数 |

## RAGFlow

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `RAGFLOW_API_URL` | string | — | RAGFlow API 地址 |
| `RAGFLOW_API_KEY` | string | — | RAGFlow API Key |

## 服务配置

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `SERVER_HOST` | string | `0.0.0.0` | 监听地址 |
| `SERVER_PORT` | int | `8000` | 监听端口 |
| `SERVER_WORKERS` | int | `1` | 工作进程数 |

## 数据同步

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `SYNC_API_TIMEOUT` | int | `30` | MES API 超时（秒） |
| `SYNC_INTERVAL_MINUTES` | int | `60` | 自动同步间隔（分） |
| `SYNC_BATCH_SIZE` | int | `100` | 每批同步数量 |

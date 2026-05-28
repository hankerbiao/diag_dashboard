# 配置参考

系统配置分散在两个地方：环境变量（`diag_backend/.env`）和厂区 YAML（`configs/factories.yaml`）。

## 环境变量

由 `app/core/config.py` 的 `Settings` 类管理，完整列表见[环境变量参考](/deployment/environment-vars)。

核心配置项：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `MONGODB_URI` | MongoDB 连接串 | `mongodb://10.17.154.252:27018` |
| `MONGODB_DB_NAME` | 数据库名 | `diag_ai` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | （必填） |
| `OPENAI_API_KEY` | LLM API Key | （可选，留空则用 mock 模式） |
| `OPENAI_API_URL` | LLM API 地址 | （可选，兼容 OpenAI 格式） |
| `AI_MODEL` | LLM 模型名 | `gemini-2.5-flash` |
| `AI_TEMPERATURE` | LLM 温度参数 | `0.3` |
| `RAGFLOW_API_URL` | RAGFlow API 地址 | （可选） |
| `RAGFLOW_API_KEY` | RAGFlow API Key | （可选） |

## 厂区配置（YAML）

`configs/factories.yaml` 是厂区配置的单一数据源，后端和独立脚本均从此文件读取。

```yaml
factories:
  - factory_id: "kunshan"
    name: "昆山厂"
    base_url: "http://10.17.154.252:8099/"
    log_base_url: "http://10.17.154.246:8080/"

  - factory_id: "shenzhen"
    name: "深圳厂"
    base_url: "http://10.17.154.253:8099/"
    log_base_url: "http://10.17.154.247:8080/"
```

每个厂区条目包含：
- **factory_id** — 厂区唯一标识
- **name** — 显示名称
- **base_url** — MES API 基础地址（同步脚本使用）
- **log_base_url** — 日志文件下载地址（诊断功能使用）

### Nginx 配置

如果 MES API 路径有特殊规则，可在 Nginx 中配置反向代理。

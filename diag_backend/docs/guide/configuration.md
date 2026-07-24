# 配置参考

配置分三类：**环境变量**（`.env`）、**厂区 YAML**、**MongoDB 运行时配置**。

## 环境变量 (.env)

由 `app/core/config.py` 的 `Settings` 加载，`get_settings()` 带 `@lru_cache`。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB 连接串 |
| `MONGODB_DB_NAME` | `diag_analysis` | 数据库名 |
| `JWT_SECRET_KEY` | （弱默认值） | HS256 签名密钥，**生产必改** |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token 有效期 |
| `OPENAI_API_KEY` | `""` | LLM API Key |
| `OPENAI_API_URL` | `""` | 兼容 OpenAI 的 base URL |
| `AI_MODEL` | `gpt-4-turbo` | 模型名 |
| `AI_TEMPERATURE` | `0.7` | |
| `GEMINI_API_KEY` | `""` | 备用 |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Uvicorn 绑定 |
| `DEBUG` | `false` | |
| `FACTORIES_YAML_PATH` | `""` | 空则自动找 `configs/factories.yaml` |
| `KNOWLEDGE_BASE_STORAGE_PATH` | `./data/knowledge_base` | 本地上传目录 |
| `RAGFLOW_API_URL` | `""` | 空则跳过 RAGFlow |
| `RAGFLOW_API_KEY` | `""` | |
| `RAGFLOW_DEFAULT_DATASET` | `weaveeye-knowledge-base` | 普通上传和历史知识数据集 |
| `RAGFLOW_TROUBLESHOOTING_DATASET` | `weaveeye-troubleshooting` | 故障排查知识数据集 |
| `RAGFLOW_REPAIR_CASE_DATASET` | `weaveeye-repair-cases` | 维修案例知识数据集 |
| `RAGFLOW_OPERATION_GUIDE_DATASET` | `weaveeye-operation-guides` | 操作规范知识数据集 |
| `RAGFLOW_FAQ_DATASET` | `weaveeye-faq` | 常见问答知识数据集 |
| `MES_REQUEST_TIMEOUT` | `30` | MES HTTP 超时秒 |
| `LOG_LEVEL` | `INFO` | |
| `LOG_FORMAT` | `console` | `console` / `json` |
| `LOG_FILE` | 无 | 设置则写文件 + 轮转 |
| `LOG_MAX_BYTES` | 50MB | |
| `LOG_BACKUP_COUNT` | 30 | |

## 厂区 YAML

路径：`configs/factories.yaml`（或通过 `FACTORIES_YAML_PATH` 覆盖）。

```yaml
factories:
  - factory_id: kunshan
    name: 昆山厂区
    base_url: http://10.8.102.88
    log_base_url: http://10.8.102.89/log
    log_ftp_user: optional
    log_ftp_password: optional
```

- `base_url` — SIMS/MES HTTP API 根路径
- `log_base_url` — HTTP 日志前缀或 `ftp://host`
- FTP 路径拼接规则见 [日志下载](/workflows/log-download) 与 `build_log_download_url()`

## MongoDB 运行时配置

| 文档位置 | 用途 |
|----------|------|
| `global_app_config` `_id: ai_config` | 全局 AI 配置（Settings 页保存） |
| `auto_sync_configs` | 各厂区 SIMS + `__mes__` MES 自动同步间隔 |
| `factory_sites` | YAML seed 的厂区元数据副本 |
| `app_settings` | 每用户设置（`user_id` unique） |

首次启动 `seed_default_data()` 会从 `.env` 写入 `ai_config`（仅 `$setOnInsert`）。

## 配置优先级（AI）

1. MongoDB `global_app_config.ai_config`（用户通过 API 保存）
2. 环境变量 `.env`
3. `LLMService` 内 mock 兜底

## RAGFlow 可选性

`ragflow_service._ok()` 检查 URL + Key；未配置时：

- 知识库上传仍写本地 + MongoDB 元数据
- 诊断时跳过 RAG 阶段或返回空引用

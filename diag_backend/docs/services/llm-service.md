# LLM 服务

**文件：** `app/services/llm_service.py`

## 职责

- 组装诊断 prompt（`app/prompts/` + 内联模板）
- 调用 OpenAI 兼容 Chat Completions API
- 无 API Key 时返回 **mock** 结构化结果（便于本地开发）

## 主要方法

| 方法 | 说明 |
|------|------|
| `diagnose(...)` | SN 诊断主入口 |
| `analyze_error_log(...)` | 异常日志分析 |
| `follow_up(...)` | 多轮追问 |

## 配置来源

1. MongoDB `global_app_config.ai_config`（优先）
2. `get_settings()` 环境变量

## Prompt 输入

- 错误日志片段（tail lines）
- knowledge_graph 检索结果
- RAGFlow 参考文档
- 设备/维修/案例上下文

## 错误处理

- HTTP 超时、4xx/5xx 记录日志并向上抛出或返回友好错误
- 测试：`tests/test_llm_service.py`

## 扩展

- 换模型：改 `model` 字段
- 换 provider：扩展 `LLMService` 分支或统一 OpenAI-compatible 网关

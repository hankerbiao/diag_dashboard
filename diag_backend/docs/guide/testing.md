# 测试

测试目录：`diag_backend/tests/`。

## 运行

```bash
cd diag_backend
pytest                          # 全部
pytest tests/test_auth_routes.py -v
pytest --cov=app --cov-report=term-missing
```

## 测试文件概览

| 文件 | 覆盖 |
|------|------|
| `test_auth_routes.py` / `test_auth_core.py` | 注册、登录、JWT |
| `test_diagnosis_routes.py` | 诊断 API |
| `test_error_logs_routes.py` | 异常看板 API |
| `test_settings_routes.py` | AI 配置 |
| `test_sync_routes.py` | 同步触发 |
| `test_build_log_url.py` | 日志 URL 拼接 |
| `test_ftp_urlopen.py` | 匿名 FTP |
| `test_validate_log_path.py` | 日志路径校验 |
| `test_error_log_detail_lookup.py` | 合成 error_log_id 解析 |
| `test_log_download.py` | 日志下载 |
| `test_llm_service.py` | LLM mock |
| `test_utils.py` | 工具函数 |
| `test_config.py` | Settings |

## 编写建议

- 路由测试用 `httpx.AsyncClient` + `app.main:app` 或 FastAPI `TestClient`
- 外部 MES/LLM/RAGFlow **必须 mock**，CI 不依赖内网
- 测 FTP/URL 逻辑用纯函数测试，不连真实 FTP

## Fixture

若 `tests/conftest.py` 存在，通常提供：

- 测试用 MongoDB（或 mock collection）
- 认证 header fixture

添加新诊断行为时，优先在 `test_*` 中加回归用例，尤其是：

- MES 返回空 `server_sn`
- SIMS 日志路径带 leading `/`
- FTP `/log//` 双斜杠前缀

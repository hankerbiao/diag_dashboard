# 配置模块 (config)

**文件：** `app/core/config.py`

使用 `pydantic-settings.BaseSettings`，从环境变量和 `.env` 加载。

## 用法

```python
from app.core.config import get_settings

settings = get_settings()  # lru_cache 单例
```

## Settings 字段

见 [配置参考](/guide/configuration) 完整表格。

## 设计说明

- **无多环境文件**：不区分 `.env.production`，由部署注入环境变量
- **`factories_yaml_path`**：空时 `factory_config` 自动解析相对 `diag_backend/configs/factories.yaml`
- **`log_dir` property**：从 `log_file` 推导目录

## 安全

- `jwt_secret_key` 默认值仅适合本地
- `.env` 已在根 `.gitignore` 忽略
- AI Key 可只存 MongoDB，不写 `.env`（生产推荐密钥管理）

## 测试

`tests/test_config.py` 验证默认值与环境覆盖。

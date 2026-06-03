# 厂区配置

**文件：** `app/core/factory_config.py`  
**数据：** `configs/factories.yaml`

## API

| 函数 | 说明 |
|------|------|
| `load_factories_from_yaml()` | 解析 YAML 返回 list[dict] |
| `get_factory_by_id(factory_id)` | 单个厂区或 None |

## YAML 结构

```yaml
factories:
  - factory_id: string   # 必填，唯一
    name: string
    base_url: string     # MES HTTP
    log_base_url: string # HTTP 或 ftp://
    log_ftp_user: optional
    log_ftp_password: optional
```

## 路径解析

1. `Settings.factories_yaml_path` 若设置则用绝对/相对路径
2. 否则查找 `diag_backend/configs/factories.yaml`

## 使用方

- `routers/factories.py` — 列表 API
- `routers/diagnosis.py` — SIMS 查询、日志下载
- `services/mes_direct_service.py` — 拼 URL
- `services/analytics_service.py` — 按厂区预计算
- `mongodb_indexes.seed_default_data` — 写 `factory_sites`
- `scripts/sync_data.py` — 离线同步

## 修改流程

1. 改 YAML
2. 重启后端（或等待 seed 对新 id upsert）
3. 无需改代码除非新增字段 consumed by MES service

## GET /api/factories

返回 YAML 中的厂区列表，供前端 Header 下拉。

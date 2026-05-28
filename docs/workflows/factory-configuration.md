# 厂区配置管理

厂区配置采用 YAML 文件作为单一数据源，后端和同步脚本共享同一配置。

## 配置存储

### sources/factories.yaml

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

## 配置读取

| 调用方 | 方式 |
|--------|------|
| 后端 `factory_config.py` | 直接读取 YAML 文件 |
| 同步脚本 `sync_data.py` | 直接读取 YAML 文件 |
| 后端启动 MongoDB seed | 读取 YAML → 写入 `factory_sites` 集合 |
| 前端 `factoryApi.list()` | GET /api/factories → 读取 YAML |

## 启动种子数据

`mongodb_indexes.py` 的 `seed_default_data()` 函数在应用启动时将 YAML 配置写入两个 MongoDB 集合：

- `factory_sites` — 厂区列表（供前端查询）
- `auto_sync_configs` — 自动同步配置

## 前端使用

```
Header 厂区选择器 → 用户选择厂区
  └→ factory_id 作为参数传递：
       ├→ ErrorLogsTab: 过滤服务器列表
       ├→ Analytics: 过滤看板数据
       └→ Diagnosis: 确定 log_base_url
```

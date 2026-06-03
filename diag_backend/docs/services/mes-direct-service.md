# MES 直连服务

**文件：** `app/services/mes_direct_service.py`

## 职责

实时 HTTP 调用各厂区 MES/SIMS API（非 sync 批量数据）。

## 用法

```python
async with MESDirectService() as mes:
    result = await mes.get_test_details(factory_id, server_sn=sn, limit=50)
```

## ServerInfo / 异常

- `MESRequestError` — 带 `debug` dict（url, params, status, body snippet）
- 诊断路由捕获后转用户可读 `ValueError`

## HTTP 细节

- 超时：`MES_REQUEST_TIMEOUT`（默认 30s）
- 部分厂区需 **Origin/Referer** 头（已在 service 配置）
- Base URL 来自 `factories.yaml` `base_url`

## 常见失败

| 现象 | 原因 |
|------|------|
| 502 Bad Gateway | 厂区 MES 服务宕机（如 datong `10.39.102.32`） |
| 连接超时 | 网络/VPN |
| 空 items | SN 不存在或厂区选错 |

## 与 sync 数据关系

- **实时**：MESDirectService → 诊断、AnalyzeContext 补拉
- **批量**：scripts → `sync_remote_*` → 看板/列表

两者数据源相同 SIMS，但路径不同。

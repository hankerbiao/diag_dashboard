# 实时 MES 数据查询方案 v3

## 状态：✅ 已实现

## 评审过程

| 版本 | 核心思路 | 被否原因 |
|------|---------|---------|
| v1 | 前端传 `realtime=true/false` 手动切换 | 多余参数，用户不需要选 |
| v2 | 后端 `AutoFallbackSource` 自动切换 MES→MongoDB | **"不要悄悄帮我切换，错了我要能排查"** |

## v3 最终方案：纯实时 + 错误透传

```
用户输入 SN / 产品型号
        │
        ▼
┌──────────────────────────┐
│   MESDirectService       │  ← 直连 MES API，唯一数据源
│                          │
│  成功 → 返回实时数据      │
│  失败 → ApiResponse(     │
│           success=false, │
│           error="MES API │
│           查询失败: 超时" │  ← 错误清晰，可排查
│         )                │
└──────────────────────────┘

MongoDB 是什么角色？
  → 看板统计聚合（analytics_service.py）
  → 同步数据存档（sync_data.py 定时写入）
  → SN 诊断中的 devices/maintenance_records（这些本身就是 MongoDB-only）
  → 和实时查询完全隔离，不碰
```

## 实现步骤

### ✅ Phase 1: MESDirectService（˜80 行）

**文件**: `app/services/mes_direct_service.py`

```python
import httpx
from ..core.factory_config import get_factory_by_id

class MESDirectService:
    """直连各厂区 MES API 的实时查询服务（无缓存、无降级）"""

    def __init__(self):
        self._clients: dict[str, httpx.AsyncClient] = {}

    def _client(self, factory_id: str) -> httpx.AsyncClient:
        if factory_id not in self._clients:
            factory = get_factory_by_id(factory_id)
            if not factory:
                raise ValueError(f"厂区不存在: {factory_id}")
            self._clients[factory_id] = httpx.AsyncClient(
                base_url=factory["base_url"],
                timeout=30,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    # 与 scripts/sync_data.py MESClient 保持一致
                },
            )
        return self._clients[factory_id]

    async def search_servers(self, factory_id: str, *, sn: str = "",
            product_models: str = "", page: int = 1, limit: int = 20) -> dict:
        """搜索服务器列表 → 直连 MES API"""
        client = self._client(factory_id)
        resp = await client.post(
            "/stepsmanagement/monitor/queryTestingServers.action",
            data={"page": page, "limit": limit, "serverSN": sn,
                  "productModels": product_models, ...},
        )
        resp.raise_for_status()
        data = resp.json()
        # 字段清洗 → 与现有 SyncService.get_servers 返回一致
        return self._normalize_servers(data.get("data", []), page, limit)

    async def get_test_details(self, factory_id: str, server_sn: str,
            limit: int = 500) -> list[dict]:
        """查询测试明细 → 直连 MES API"""
        ...

    def _normalize_servers(self, raw: list[dict], page, limit) -> dict:
        """字段映射，保证与现有 API 响应格式兼容"""
        ...
```

关键设计：
- **无缓存**：每次调用都直连 MES
- **无 fallback**：MES 出错直接 raise，让路由层转成 `ApiResponse(success=false, error=...)`
- **连接池复用**：按厂区缓存 `httpx.AsyncClient`，避免每次创建连接
- **字段兼容**：输出格式与 `SyncService` 一致 → 前端不动

### ✅ Phase 2: 接入 SN 诊断 (`routers/diagnosis.py`)

修改 `_gather_sn_data`，将中间的测试日志数据来源从 MongoDB 切为 MES：

```python
# 改前（第 83-84 行）：
raw_logs = await col.find({"server_sn": sn}).sort("test_time", -1).limit(50).to_list(50)

# 改后：
mes = MESDirectService()
try:
    raw_logs = await mes.get_test_details(factory, server_sn=sn, limit=50)
except Exception as e:
    raise ValueError(f"MES 查询失败 [{factory}]: {e}。请确认 SN 正确且厂区 MES 可达。")
```

### ✅ Phase 3: 接入服务器搜索 (`routers/sync.py`)

改造 `GET /api/sync/servers`：

```python
@router.get("/servers")
async def get_servers(...):
    if not factory_id:
        return ApiResponse(success=True, data={"items": [], "total": 0, ...})
    try:
        svc = MESDirectService()
        result = await svc.search_servers(factory_id=factory_id, sn=search_sn, ...)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, error=f"MES API 查询失败: {e}")
```

### ✅ Phase 4: 配置化 `core/config.py`

```python
mes_request_timeout: int = 30  # MES 实时查询超时秒数
```

不设 `data_source_mode` 切换开关 — 因为实时就是实时，不需要切。

---

## 错误信息设计

MES 不可用时，前端收到的错误不是笼统的"查询失败"，而是带上下文：

| 场景 | 错误信息 |
|------|---------|
| 厂区 MES 超时 | `MES 查询失败 [kunshan]: ConnectionTimeout。请检查厂区网络。` |
| SN 不存在 | `MES 查询失败 [tianjin2]: 未找到 SN=XXX123 的相关数据。` |
| 厂区未配置 | `厂区不存在: unknown_factory` |
| 参数错误 | `缺少 factory 参数，实时查询必须指定厂区` |

---

## 文件清单

| 文件 | 动作 | 行数 |
|------|------|------|
| `app/services/mes_direct_service.py` | **新建** | ~200 |
| `app/routers/diagnosis.py` | 修改 `_gather_sn_data` 的数据源 | ±10 |
| `app/routers/sync.py` | 修改 `/servers` 和 `/servers/{sn}/test-details` 改用实时数据源 | ±30 |
| `app/core/config.py` | 增加 `mes_request_timeout` | +2 |

**前端改动：0 行。**

## 验证

```bash
# SN 诊断（实时走 MES）
curl -X POST http://localhost:8000/api/diagnosis/sn \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"sn":"2026HTBWTEST0148","factory":"kunshan"}'

# 服务器搜索（实时走 MES）
curl "http://localhost:8000/api/sync/servers?factory_id=kunshan&search_sn=2026HTBW"

# 模拟 MES 故障 → 应返回明确错误，不降级
# 临时改 factories.yaml 中 kunshan 的 base_url 为 http://10.255.255.1
# → 应得到 success=false, error="MES 查询失败 [kunshan]: ..."
```

---

## 实现日期

2026-06-02
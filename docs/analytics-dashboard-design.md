# 批量测试异常看板 — 数据图表设计文档

## 1. 概述

为异常看板搜索结果页增加数据聚合图表，提供测试质量的多维度分析视图。数据源为 `sync_remote_test_details` MongoDB 集合。

## 2. 数据字段

`sync_remote_test_details` 中可用于图表的字段：

| 字段 | 类型 | 说明 | 适合场景 |
|------|------|------|---------|
| `fault_type1` | string | 主故障类别 | 分布饼图 |
| `fault_type2` | string | 故障子类别 | 细分柱状图 |
| `fault_type3` | string | 故障细节 | 下钻分析 |
| `server_test_result` | string | 测试结果（成功/失败） | 良率计算 |
| `decision` | string | 判定结论（PASS/FAIL等） | 决策分布 |
| `big_flow` | string | 顶层工艺流程 | 按工艺段分析 |
| `detailed_flow` | string | 具体工站名称 | 工站失败排行 |
| `test_time` | datetime | 测试时间 | 时间序列X轴 |
| `server_sn` | string | 服务器SN | 关联/过滤 |
| `product_models` | string | 产品型号（来自 servers 表） | 机型不良率 |

## 3. 图表设计（6张）

### Chart 1: 故障主类别分布
- **类型**: 环形饼图（Donut PieChart）
- **数据**: `$group by fault_type1 → count`, 取 TOP10
- **图表库**: recharts `<PieChart>` + `<Pie innerRadius={50} outerRadius={80}>`
- **图标**: Bug (rose-500)
- **空状态**: "暂无故障类别数据"

### Chart 2: 故障子类别 TOP10
- **类型**: 水平柱状图（Horizontal BarChart）
- **数据**: `$group by fault_type2 → count`, where fault_type2 != "", 取 TOP10
- **图表库**: recharts `<BarChart layout="vertical">` + `<LabelList>`
- **图标**: ListTree (amber-500)
- **空状态**: "暂无故障子类别数据"

### Chart 3: 日良率趋势
- **类型**: 面积图（AreaChart）
- **数据**: `$group by date(test_time) → total, passed(server_test_result="成功"), failed → yield% = passed/total*100`
- **图表库**: recharts `<AreaChart>` + `<Area>` 渐变填充, Y轴 domain=[80,100], tickFormatter 加 % 
- **图标**: TrendingUp (emerald-500)
- **空状态**: "暂无良率趋势数据"

### Chart 4: 工站失败数 TOP10
- **类型**: 垂直柱状图（Vertical BarChart）
- **数据**: `$group by detailed_flow → count`, where server_test_result != "成功", 取 TOP10
- **图表库**: recharts `<BarChart>` + `<Bar dataKey="count">` + `<LabelList position="top">`
- **图标**: Server (blue-500)
- **空状态**: "暂无工站失败数据"

### Chart 5: 判定结果分布
- **类型**: 饼图（PieChart）
- **数据**: `$group by decision → count`, where decision != ""
- **图表库**: recharts `<PieChart>` + `<Pie>`, Cell 条件着色 (PASS=绿, FAIL=红, 其他=灰)
- **图标**: CheckCircle2 (violet-500)
- **空状态**: "暂无判定数据"

### Chart 6: 机型不良率
- **类型**: 组合图（ComposedChart: 柱状图 + 折线图）
- **数据**: `$lookup sync_remote_servers → $group by product_models → total, failed → fail_rate%`
- **图表库**: recharts `<ComposedChart>` + `<Bar>` + `<Line yAxisId="right">` 双Y轴
- **图标**: Cpu (indigo-500)
- **空状态**: "暂无机型数据"

## 4. 配色方案

```typescript
const CHART_COLORS = ['#ef4444', '#f97316', '#f59e0b', '#3b82f6', '#8b5cf6'];
// 复用自 src/data/mockData.ts
```

## 5. 后端 API

### 端点: `GET /api/analytics/insights`

查询参数:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `search_sn` | string? | - | 服务器SN模糊过滤 |
| `search_product_models` | string? | - | 产品型号过滤 |
| `days` | int | 30 | 回溯天数 (1-365) |

响应格式:
```json
{
  "success": true,
  "data": {
    "fault_categories": [{ "name": "...", "count": 123 }],
    "fault_subcategories": [{ "name": "...", "count": 123 }],
    "yield_trend": [{ "date": "2026-05-01", "total": 500, "passed": 480, "failed": 20, "yield": 96.0 }],
    "station_failures": [{ "station": "...", "count": 123 }],
    "decision_distribution": [{ "decision": "PASS", "count": 123 }],
    "model_defects": [{ "model": "...", "total": 500, "failed": 20, "fail_rate": 4.0 }]
  }
}
```

### 后端文件

**新建 `app/services/analytics_service.py`**:
```python
class AnalyticsService:
    async def get_dashboard_insights(search_sn, search_product_models, days) -> dict
    async def _agg_fault_categories(col, match_filter) -> list[dict]
    async def _agg_fault_subcategories(col, match_filter) -> list[dict]
    async def _agg_yield_trend(col, match_filter) -> list[dict]
    async def _agg_station_failures(col, match_filter) -> list[dict]
    async def _agg_decision_distribution(col, match_filter) -> list[dict]
    async def _agg_model_defects(details_col, servers_col, match_filter) -> list[dict]
```

每个聚合方法使用 MongoDB Aggregation Pipeline: `$match → $group → $sort → $limit → $project`

`get_dashboard_insights` 使用 `asyncio.gather` 并行执行 6 个管道。

**新建 `app/routers/analytics.py`**:
```python
router = APIRouter(prefix="/analytics", tags=["数据分析"])

@router.get("/insights")
async def get_dashboard_insights(...)
```

**修改 `app/main.py`** — 注册路由 `app.include_router(analytics_router.router, prefix="/api")`

**修改 `app/core/mongodb_indexes.py`** — 增加 3 个索引:
```python
await db["sync_remote_test_details"].create_index([("fault_type1", 1), ("test_time", -1)])
await db["sync_remote_test_details"].create_index([("server_test_result", 1), ("test_time", -1)])
await db["sync_remote_test_details"].create_index([("detailed_flow", 1), ("server_test_result", 1)])
```

## 6. 前端组件

### 新建目录: `src/components/error-logs/charts/`

共 7 个文件:

| 文件 | 说明 |
|------|------|
| `BatchFaultPieChart.tsx` | 故障类别环形图 |
| `BatchSubfaultBarChart.tsx` | 故障子类别水平柱状图 |
| `BatchYieldTrendChart.tsx` | 良率趋势面积图 |
| `BatchStationBarChart.tsx` | 工站失败垂直柱状图 |
| `BatchDecisionPieChart.tsx` | 判定分布饼图 |
| `BatchModelBarChart.tsx` | 机型不良率组合图 |
| `BatchTestCharts.tsx` | 容器组件，2x3 网格布局 |

### 组件模板（每个图表遵循）:

```tsx
interface ChartProps {
  data: ChartDataItem[];
  loading?: boolean;
}

export default function ChartName({ data, loading }: ChartProps) {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  // 派生 textColor, gridColor, bgColor, borderColor, tooltipBg

  if (loading) return <Skeleton />;  // animate-pulse
  if (data.length === 0) return <EmptyState />;

  return (
    <div className="rounded-lg shadow-sm border p-5 flex flex-col min-h-[260px]"
      style={{ backgroundColor: bgColor, borderColor }}>
      <h3 className="text-[14px] font-bold flex items-center gap-2 mb-4">
        <Icon className="w-4 h-4 text-xxx-500" />
        图表标题
      </h3>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          {/* recharts component */}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

### 容器组件 `BatchTestCharts.tsx`:

```tsx
interface BatchTestChartsProps {
  data: DashboardInsights | null;
  loading: boolean;
}
// 2x3 网格: grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4
// data 为 null 且非 loading → 不渲染
// loading → 显示 6 个骨架占位
// 有数据 → 渲染 6 个图表
```

### API 类型（添加到 `src/api/fastapi.ts`）:

```typescript
interface FaultCategoryItem { name: string; count: number; }
interface YieldTrendItem { date: string; total: number; passed: number; failed: number; yield: number; }
interface StationFailureItem { station: string; count: number; }
interface DecisionDistributionItem { decision: string; count: number; }
interface ModelDefectItem { model: string; total: number; failed: number; fail_rate: number; }
interface DashboardInsights {
  fault_categories: FaultCategoryItem[];
  fault_subcategories: FaultCategoryItem[];
  yield_trend: YieldTrendItem[];
  station_failures: StationFailureItem[];
  decision_distribution: DecisionDistributionItem[];
  model_defects: ModelDefectItem[];
}

const analyticsApi = {
  getInsights(params?: { search_sn?: string; search_product_models?: string; days?: number })
    : Promise<ApiResponse<DashboardInsights>>
};
```

## 7. ErrorLogsTab 集成

**修改 `ErrorLogsTab.tsx`**:

1. 新增 state:
```typescript
const [insights, setInsights] = useState<DashboardInsights | null>(null);
const [insightsLoading, setInsightsLoading] = useState(false);
```
2. 在搜索处理中并行请求 analytics:
```typescript
// 与 getServers 并行（或用 Promise.all）
const insightsRes = await analyticsApi.getInsights({ search_sn: sn, days: 30 });
if (insightsRes.success) setInsights(insightsRes.data);
```
3. 在服务器列表下方插入图表:
```tsx
{isSearched && (
  <div className="flex-1 flex flex-col min-h-0 overflow-y-auto">
    {/* 服务器列表 — 固定高度 max-h-[500px] */}
    <div className="mx-4 mb-4 ...">
      ...
    </div>
    {/* 图表区 */}
    <BatchTestCharts data={insights} loading={insightsLoading} />
  </div>
)}
```

## 8. 注意事项

- `test_time` 在 MongoDB 中是 ISO 字符串，聚合管道需用 `$dateFromString` 转换，或直接按字符串前缀分组（YYYY-MM-DD）
- `fault_type1/2` 有空值情况，管道需过滤 `{"$ne": ""}`
- `product_models` 在 `sync_remote_servers` 表中，需通过 `$lookup` 关联
- 图表组件必须支持暗色模式（通过 `useTheme()` 获取）
- 每个图表组件必须具备 loading / empty / 正常数据 三种状态

## 9. 图表库

已安装 **recharts v3.8.1**，现有图表参考见 `src/components/dashboard/charts/` 目录。

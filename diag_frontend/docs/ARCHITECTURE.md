# WeaveEye 后端架构设计方案

## 技术选型
- **Supabase**: PostgreSQL 数据库、实时订阅、认证、RLS 权限控制
- **FastAPI**: AI 推理服务、业务逻辑、API 网关

## 分工原则

| 层级 | Supabase | FastAPI |
|------|----------|---------|
| 数据存储 | PostgreSQL | - |
| 实时数据 | 实时订阅 | - |
| 认证授权 | Auth + RLS | JWT 验证 |
| CRUD 操作 | 直接 SQL/RPC | - |
| AI 推理 | - | 独占 |
| 外部集成 | - | LLM API |
| 业务逻辑 | Edge Functions | 主逻辑 |

---

## 数据库设计 (Supabase)

### 表结构

```sql
-- 1. 厂区配置
CREATE TABLE factories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT UNIQUE NOT NULL,  -- 'TJ', 'TJ3', 'PJ1'...
  name TEXT NOT NULL,         -- '天津', '天津三期'...
  region TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. 设备档案
CREATE TABLE devices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sn TEXT UNIQUE NOT NULL,
  model TEXT NOT NULL,
  factory_id UUID REFERENCES factories(id),
  batch TEXT,                  -- 批次号
  production_date DATE,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. 测试异常日志
CREATE TABLE error_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID REFERENCES devices(id),
  factory_id UUID REFERENCES factories(id),
  test_item TEXT NOT NULL,
  test_time TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL,        -- '失败', '通过'
  user_choice TEXT,            -- '跳过', '-'
  mes_reported BOOLEAN DEFAULT false,
  fail_details TEXT,
  order_no TEXT,               -- 生产订单号
  model_name TEXT,             -- 机型名称
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 4. 历史维修记录
CREATE TABLE maintenance_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID REFERENCES devices(id),
  date DATE NOT NULL,
  component TEXT NOT NULL,
  action TEXT NOT NULL,
  technician TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 5. 诊断记录
CREATE TABLE diagnosis_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id UUID REFERENCES devices(id),
  factory_id UUID REFERENCES factories(id),
  category TEXT,
  summary TEXT,
  confidence FLOAT,
  suggestions JSONB,
  reference_logs JSONB,
  maintenance_history JSONB,
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 6. 知识库 - 历史案例
CREATE TABLE case_library (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  error_code TEXT,
  root_cause TEXT,
  repair_steps JSONB,
  similarity_tags TEXT[],
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 7. 系统配置
CREATE TABLE app_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) UNIQUE,
  ai_api_url TEXT DEFAULT 'https://api.openai.com/v1',
  ai_api_key TEXT,
  ai_model TEXT DEFAULT 'gpt-4-turbo',
  ai_temperature FLOAT DEFAULT 0.7,
  active_kbs TEXT[] DEFAULT ARRAY['MES', 'SIMS', 'Case Library'],
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- 索引
CREATE INDEX idx_error_logs_factory ON error_logs(factory_id);
CREATE INDEX idx_error_logs_test_time ON error_logs(test_time);
CREATE INDEX idx_error_logs_sn ON error_logs(device_id);
CREATE INDEX idx_devices_sn ON devices(sn);
CREATE INDEX idx_diagnosis_device ON diagnosis_records(device_id);
```

### RLS 策略 (行级安全)

```sql
-- 设备按厂区隔离
ALTER TABLE devices ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view devices in their factory"
  ON devices FOR SELECT
  USING (
    factory_id IN (
      SELECT factory_id FROM user_factory_access WHERE user_id = auth.uid()
    )
  );

-- 异常日志按厂区隔离
ALTER TABLE error_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view error logs in their factory"
  ON error_logs FOR SELECT
  USING (
    factory_id IN (
      SELECT factory_id FROM user_factory_access WHERE user_id = auth.uid()
    )
  );
```

---

## API 架构

### Supabase 直接访问 (前端 → Supabase)

```typescript
// 前端直接调用 Supabase
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

// 1. 异常日志查询 (CRUD 直接走 Supabase)
const { data, error } = await supabase
  .from('error_logs')
  .select('*, devices(sn, model)')
  .eq('factory_id', factoryId)
  .gte('test_time', startDate)
  .lte('test_time', endDate)

// 2. 统计数据 (使用 Supabase RPC)
const { data } = await supabase.rpc('get_error_stats_by_type', {
  p_factory_id: factoryId,
  p_time_range: 'day'
})

// 3. 设备信息查询
const { data } = await supabase
  .from('devices')
  .select('*')
  .eq('sn', sn)
  .single()
```

### FastAPI 服务 (AI + 业务逻辑)

```
fastapi/
├── main.py                    # 应用入口
├── routers/
│   ├── diagnosis.py           # 诊断相关 API
│   ├── error_logs.py          # 异常日志增强 API
│   ├── knowledge.py           # 知识库 API
│   └── settings.py            # 配置管理 API
├── services/
│   ├── llm_service.py         # LLM 调用封装
│   ├── knowledge_graph.py     # 知识图谱检索
│   └── diagnosis_engine.py    # 诊断引擎
├── models/
│   ├── request.py             # 请求模型
│   └── response.py            # 响应模型
├── core/
│   ├── config.py              # 配置管理
│   ├── security.py            # JWT 验证
│   └── supabase.py            # Supabase 客户端
└── prompts/
    └── diagnosis_prompt.py    # AI 提示词
```

#### FastAPI 路由设计

```python
# routers/diagnosis.py

@router.post("/diagnosis/sn")
async def diagnose_by_sn(sn: str, factory: str):
    """
    单机 SN 深度诊断
    1. 查询设备信息
    2. 查询测试日志
    3. 查询维修记录
    4. 调用 LLM 生成诊断结果
    """
    # 获取设备信息
    device = await get_device_by_sn(sn)

    # 获取 SIMS 测试日志
    test_logs = await get_test_logs(device.id)

    # 获取历史维修记录
    maintenance = await get_maintenance_history(device.id)

    # 调用诊断引擎
    result = await diagnosis_engine.analyze(
        device=device,
        test_logs=test_logs,
        maintenance=maintenance
    )

    # 保存诊断记录
    await save_diagnosis_record(result)

    return result

@router.post("/diagnosis/error-log/{error_log_id}")
async def analyze_error_log(error_log_id: str):
    """
    异常日志 AI 分析
    """
    error_log = await get_error_log(error_log_id)

    # 检索相似案例
    similar_cases = await knowledge_graph.find_similar(error_log.fail_details)

    # 调用 LLM 分析
    analysis = await llm_service.analyze_error(error_log, similar_cases)

    return {
        "error_log": error_log,
        "analysis": analysis,
        "similar_cases": similar_cases
    }
```

```python
# routers/error_logs.py

@router.get("/error-logs/stats/trend")
async def get_error_trend(
    factory: str,
    time_range: Literal["day", "week", "month"]
):
    """
    阻断历史趋势统计
    """
    data = await supabase.rpc('get_error_trend', {
        p_factory: factory,
        p_range: time_range
    })
    return data

@router.get("/error-logs/stats/yield")
async def get_yield_trend(factory: str):
    """
    直通率趋势
    """
    return await supabase.rpc('get_yield_trend', { p_factory: factory })
```

### 认证流程

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  前端    │────▶│ Supabase │────▶│ FastAPI  │
│          │     │   Auth   │     │          │
│          │◀────│          │◀────│          │
│          │ JWT │          │     │          │
└──────────┘     └──────────┘     └──────────┘
```

```python
# core/security.py
from supabase import create_client
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    """验证 Supabase JWT Token"""
    supabase = get_supabase_client()

    # 验证 token 并获取用户
    user = supabase.auth.get_user(token.credentials)

    if not user:
        raise HTTPException(401, "Invalid token")

    return user

@router.post("/diagnosis/sn")
async def diagnose_sn(
    sn: str,
    factory: str,
    user = Depends(get_current_user)
):
    """带认证的诊断接口"""
    # user.id 可用于记录操作者
    ...
```

---

## 实时订阅 (Supabase)

```typescript
// 前端订阅异常日志变化
useEffect(() => {
  const channel = supabase
    .channel('error_logs_changes')
    .on(
      'postgres_changes',
      {
        event: '*',
        schema: 'public',
        table: 'error_logs',
        filter: `factory_id=eq.${factoryId}`
      },
      (payload) => {
        // 实时更新列表
        setErrorLogs(prev => updateOrInsert(prev, payload.new))
      }
    )
    .subscribe()

  return () => {
    supabase.removeChannel(channel)
  }
}, [factoryId])
```

---

## 实施计划

### Phase 1: Supabase 基础配置 (预计 2h)
1. 创建 Supabase 项目
2. 创建数据库表
3. 配置 RLS 策略
4. 配置 Auth (可选)
5. 插入初始数据

### Phase 2: FastAPI 基础架构 (预计 2h)
1. 项目结构搭建
2. Supabase 客户端封装
3. JWT 认证中间件
4. 基础路由框架

### Phase 3: AI 诊断服务 (预计 4h)
1. LLM 服务封装 (支持 OpenAI/Gemini)
2. 诊断提示词设计
3. 知识图谱检索实现
4. 诊断 API 完成

### Phase 4: 前后端对接 (预计 3h)
1. 前端 API 服务层
2. 异常日志查询对接
3. AI 诊断流程对接
4. 设置页面对接

### Phase 5: 优化与测试 (预计 2h)
1. 性能优化 (缓存、索引)
2. 错误处理完善
3. 单元测试

---

## 文件结构

```
diag_ai_analysis/
├── diag_frontend/          # 现有前端
│   └── src/
│       ├── api/            # 新增: API 服务层
│       │   ├── supabase.ts
│       │   └── fastapi.ts
│       └── ...
│
└── diag_backend/           # 新增: FastAPI 后端
    ├── app/
    │   ├── __init__.py
    │   ├── main.py
    │   ├── config.py
    │   ├── routers/
    │   │   ├── __init__.py
    │   │   ├── diagnosis.py
    │   │   ├── error_logs.py
    │   │   └── settings.py
    │   ├── services/
    │   │   ├── __init__.py
    │   │   ├── llm_service.py
    │   │   └── knowledge_graph.py
    │   ├── models/
    │   │   ├── __init__.py
    │   │   ├── request.py
    │   │   └── response.py
    │   └── core/
    │       ├── __init__.py
    │       ├── config.py
    │       ├── security.py
    │       └── supabase.py
    ├── tests/
    ├── .env.example
    ├── requirements.txt
    └── README.md
```

---

## 环境变量

```bash
# .env (FastAPI)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJxxx
SUPABASE_SERVICE_KEY=eyJxxx
OPENAI_API_KEY=sk-xxx
GEMINI_API_KEY=xxx

# .env.local (前端)
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJxxx
VITE_API_BASE_URL=http://localhost:8000
```
# AI 诊断分析

WeaveEye 的核心功能。用户从异常日志中选择一条失败记录，系统通过 3 阶段管道进行分析：**日志下载 → 知识库检索 → LLM 推理**。

## 触发路径

### SN 诊断（POST /api/diagnosis/sn）

一次性非流式响应，适合通过 SN 全面诊断一台设备：

```
1. 查询设备信息 → knowledge_graph.get_device_by_sn()
2. 查询测试日志 → get_device_test_logs()
3. 查询维修记录 → get_device_maintenance_history()
4. 检索相似案例 → find_similar_cases()
5. 调用 LLM 生成诊断结果
```

### 智能诊断剖析（POST /api/diagnosis/error-log/{id}/analyze）

SSE 流式响应，适合对单条测试记录做深度分析：

```
1. 检查 diagnosis_cache（命中则直接返回）
2. 3 阶段管道（download → ragflow → llm）
3. 写入缓存后返回结果
```

## SSE 协议

| 事件类型 | 数据负载 | 阶段 |
|---------|----------|------|
| `progress` | `{"stage":"download","detail":"..."}` | 日志下载 |
| `progress` | `{"stage":"ragflow","detail":"..."}` | 知识库检索 |
| `progress` | `{"stage":"llm","detail":"..."}` | LLM 推理 |
| `token` | `{"text":"..."}` | LLM 流式输出 |
| `done` | `{"success":true,"data":{...}}` | 完成 |
| `error` | `{"message":"..."}` | 错误 |

前端 SSE 客户端：`diagnosisApi.analyzeSSE()`

## 3 阶段管道

### 阶段 1：日志下载

- 函数：`_download_log_tail()` (`diagnosis.py:174`)
- 使用 `httpx.AsyncClient` 从 `log_base_url` 获取文件
- 普通日志：2MB 截断 + 尾部 50 行
- HTML 日志：使用 `lxml` 移除 script/style 标签后提取纯文本
- 日志路径不可用时静默降级

### 阶段 2：知识库检索

- 构建搜索关键词：`fail_details + test_item + fault_type1/2/3`
- 调用 `ragflow_service.search_kubernetes(question, top_k=10)`
- 按文档名（`doc_name`）去重，同一文档的多个 chunk 合并
- 检索失败时降级，不影响诊断继续

### 阶段 3：LLM 诊断推理

- 系统提示词：`"你是一个专业的硬件故障诊断专家"`
- 调用 `LLMService.analyze_with_knowledge_stream()` (`llm_service.py:220`)
- 流式 chat completion API（兼容 OpenAI/Gemini 格式）
- 模型返回 JSON，包含 5 个字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `root_cause` | string | 根本原因（简明扼要） |
| `evidence` | string[] | 关键证据列表（日志行 → 结论映射） |
| `analysis` | string | 详细分析摘要（可含 `[参考 N]` 标记） |
| `repair_suggestions` | string[] | 维修建议（3-5 条） |
| `knowledge_refs` | object[] | 引用的知识库条目 |

- JSON 解析失败时回退到 mock 模式

## 诊断缓存

| 属性 | 说明 |
|------|------|
| 集合 | `diagnosis_cache` |
| 键 | `error_log_id`（唯一） |
| 写入时机 | 每次成功分析后 |
| 缓存命中 | 跳过整个管道，直接返回 |
| 清除时机 | 通过 `re-analyze` 端点 |

## 前端实现

### AnalysisModal（`AnalysisModal.tsx`）

- **进度管道**：3 阶段 UI，显示已完成/进行中/待处理状态
- **流式文本**：在 dark terminal 风格的 `<pre>` 中实时显示
- **结果渲染**：
  - 核心根因 → 彩色高亮区块
  - 关键证据 → 深色背景编号列表
  - 详细分析 → 可点击 `[参考 N]` 标记（紫色徽章 + 悬停来源提示）
  - 修复建议 → 绿色编号列表
  - 知识库参考 → 可折叠 `<details>` 组件
- **缓存标注**：结果来自缓存时显示 `（缓存结果）` 标签
- **重新生成**：清除缓存后重新执行完整管道

### 时序图

```
Frontend                    Backend                     Storage
   │                           │                           │
   │ POST /analyze?log_base_url│                           │
   │──────────────────────────▶│                           │
   │                           │── check diagnosis_cache─▶│ MongoDB
   │                           │◀── miss/hit ─────────────│
   │                           │                           │
   │ event:progress(download)  │                           │
   │◀──────────────────────────│                           │
   │                           │── get_error_log_detail ─▶│ MongoDB
   │                           │                          │
   │                           │── download_log_tail() ──▶│ MES Server
   │                           │                          │
   │ event:progress(ragflow)   │                           │
   │◀──────────────────────────│                           │
   │                           │── search_knowledge_base▶│ RAGFlow API
   │                           │                          │
   │ event:progress(llm)       │                           │
   │ event:token(...)          │                           │
   │◀──────────────────────────│                           │
   │                           │── LLM stream ───────────▶│ OpenAI/Gemini
   │                           │                          │
   │                           │── save diagnosis_cache ─▶│ MongoDB
   │                           │                          │
   │ event:done({result})     │                           │
   │◀──────────────────────────│                           │
```

## 关键代码文件

| 文件 | 作用 |
|------|------|
| `app/routers/diagnosis.py` | SSE 端点，3 阶段管道，缓存读写 |
| `app/services/llm_service.py` | LLM 调用封装（流式/非流式，mock 模式） |
| `app/services/ragflow_service.py` | RAGFlow 检索封装 |
| `src/api/fastapi.ts` | 前端 SSE 客户端（`analyzeSSE` 方法） |
| `src/components/error-logs/AnalysisModal.tsx` | 诊断结果弹窗 UI |

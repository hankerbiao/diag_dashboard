# 诊断 API

## POST /api/diagnosis/sn

单机 SN 深度诊断（非流式）。

**Request:**
```json
{
  "sn": "SN20240101",
  "factory": "kunshan"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "sn": "SN20240101",
    "category": "内存故障",
    "summary": "DIMM 插槽 4 发生结构性硬件故障",
    "confidence": 0.92,
    "suggestions": ["更换内存条", "执行强化测试"],
    "maintenance_history": [...]
  }
}
```

## POST /api/diagnosis/error-log/{id}

传统异常日志分析（非流式）。

## POST /api/diagnosis/error-log/{id}/analyze

智能诊断剖析（SSE 流式）。

**Query Parameters:**
| 参数 | 说明 |
|------|------|
| `log_base_url` | 日志文件下载基础 URL |

**流程**:
1. 检查 `diagnosis_cache`，命中则直接返回缓存
2. 3 阶段管道：`download → ragflow → llm`
3. SSE 事件流推送

**Response（done 事件 data 字段）:**
```json
{
  "id": "cache_id",
  "error_log_id": "log_id",
  "sn": "SN20240101",
  "test_item": "内存测试",
  "root_cause": "ECC 校验错误导致系统崩溃",
  "evidence": [
    "日志第45行 'ECC uncorrectable error at 0x4F' → DIMM 插槽4故障"
  ],
  "analysis": "详细分析内容 [参考 1]",
  "repair_suggestions": ["更换内存条", "清除 ECC 寄存器"],
  "knowledge_refs": [{"source": "内存故障手册", "content": "..."}],
  "log_content": "日志尾部内容...",
  "created_at": "2024-01-01T00:00:00",
  "is_cached": false
}
```

## POST /api/diagnosis/error-log/{id}/re-analyze

重新生成诊断。清除 `diagnosis_cache` 后走完整 SSE 分析流程。

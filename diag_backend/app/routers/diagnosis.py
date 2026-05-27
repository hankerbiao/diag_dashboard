import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ..core.auth import get_current_user
from ..core.mongodb import get_collection
from ..models.request import DiagnosisBySNRequest, DiagnosisByErrorLogRequest
from ..models.response import ApiResponse, DiagnosisCacheResponse, DiagnosisResponse, ErrorAnalysisResponse
from ..services.llm_service import llm_service
from ..services.knowledge_graph import knowledge_graph
from ..services import ragflow_service

logger = logging.getLogger(__name__)

MAX_LOG_BYTES = 2 * 1024 * 1024
LOG_TAIL_LINES = 50
RAG_TOP_K = 10

router = APIRouter(prefix="/diagnosis", tags=["诊断"])


# ── SSE 工具 ──

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── 通用诊断 ──

@router.post("/sn", response_model=ApiResponse)
async def diagnose_by_sn(request: DiagnosisBySNRequest, current_user: dict = Depends(get_current_user)):
    try:
        device = await knowledge_graph.get_device_by_sn(request.sn)
        if not device:
            return ApiResponse(success=False, error="未找到设备信息")

        test_logs = await knowledge_graph.get_device_test_logs(device["id"])
        maintenance = await knowledge_graph.get_device_maintenance_history(device["id"])
        similar_cases = await knowledge_graph.find_similar_cases(
            ",".join([l.get("fail_details", "") for l in test_logs[:5]]))

        diagnosis = await llm_service.diagnose_sn(request.sn, device, test_logs, maintenance, similar_cases)

        return ApiResponse(success=True, data=DiagnosisResponse(
            sn=request.sn, category=diagnosis.get("category", "未知"),
            summary=diagnosis.get("summary", ""), confidence=diagnosis.get("confidence", 0.5),
            suggestions=diagnosis.get("suggestions", []), reference_logs=[],
            maintenance_history=[{"id": m.get("id", ""), "date": m.get("date", ""),
                                  "component": m.get("component", ""), "action": m.get("action", "")}
                                 for m in maintenance[:5]]))
    except Exception as e:
        return ApiResponse(success=False, error=f"诊断失败: {e}")


@router.post("/error-log/{error_log_id}", response_model=ApiResponse)
async def analyze_error_log(error_log_id: str, current_user: dict = Depends(get_current_user)):
    try:
        error_log = await knowledge_graph.get_error_log_by_id(error_log_id)
        if not error_log:
            return ApiResponse(success=False, error="未找到异常日志")

        similar_cases = await knowledge_graph.find_similar_cases(error_log.get("fail_details", ""))
        analysis = await llm_service.analyze_error(error_log, similar_cases)

        return ApiResponse(success=True, data=ErrorAnalysisResponse(
            error_log=error_log, analysis=analysis.get("analysis", ""),
            root_cause=analysis.get("root_cause", ""), repair_suggestions=analysis.get("repair_suggestions", []),
            similar_cases=similar_cases))
    except Exception as e:
        return ApiResponse(success=False, error=f"分析失败: {e}")


# ── 辅助函数 ──

async def _get_error_log_detail(error_log_id: str) -> Optional[dict]:
    col = get_collection("sync_remote_test_details")
    try:
        doc = await col.find_one({"_id": ObjectId(error_log_id)})
        if doc:
            return {
                "id": str(doc["_id"]), "sn": doc.get("server_sn", ""),
                "test_item": doc.get("detailed_flow", doc.get("big_flow", "")),
                "test_time": doc.get("test_time", ""), "fail_details": doc.get("server_test_result", ""),
                "fault_type1": doc.get("fault_type1", ""), "fault_type2": doc.get("fault_type2", ""),
                "fault_type3": doc.get("fault_type3", ""), "log_path": doc.get("log_path", ""),
            }
    except Exception:
        pass
    return await knowledge_graph.get_error_log_by_id(error_log_id)


async def _download_log_tail(log_base_url: str, log_path: str, tail_lines: int = LOG_TAIL_LINES) -> str:
    if not log_base_url or not log_path:
        return ""
    url = f"{log_base_url.rstrip('/')}/{log_path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text

            if url.endswith(".html"):
                try:
                    from lxml import html as lxml_html
                    tree = lxml_html.fromstring(text)
                    for tag in ('script', 'style'):
                        for elem in list(tree.iter(tag)):
                            elem.drop_tree()
                    lines = [l for l in tree.text_content().strip().splitlines() if l.strip()]
                    return "\n".join(lines)
                except Exception as e:
                    logger.warning("HTML 解析失败: %s", e)

            if len(text) > MAX_LOG_BYTES:
                text = text[-MAX_LOG_BYTES:]
            lines = text.splitlines()
            return "\n".join(lines[-tail_lines:] if len(lines) > tail_lines else lines)
    except Exception as e:
        logger.warning("日志下载失败 [%s]: %s", url, e)
        return ""


def _build_cache_response(result: dict, log_id: str, sn: str, test_item: str, now: str) -> dict:
    return DiagnosisCacheResponse(
        id=str(result.inserted_id), error_log_id=log_id, sn=sn, test_item=test_item,
        root_cause=result.get("root_cause", ""), evidence=result.get("evidence", []),
        analysis=result.get("analysis", ""), repair_suggestions=result.get("repair_suggestions", []),
        knowledge_refs=result.get("knowledge_refs", []), log_content=result.get("log_content", ""),
        created_at=now, is_cached=False,
    ).model_dump()


async def _build_cached_response(cached: dict) -> dict:
    return DiagnosisCacheResponse(
        id=str(cached["_id"]), error_log_id=cached["error_log_id"], sn=cached["sn"],
        test_item=cached["test_item"], root_cause=cached["root_cause"],
        evidence=cached.get("evidence", []), analysis=cached["analysis"],
        repair_suggestions=cached["repair_suggestions"], knowledge_refs=cached.get("knowledge_refs", []),
        log_content=cached.get("log_content", ""), created_at=cached["created_at"], is_cached=True,
    ).model_dump()


# ── 核心诊断逻辑 ──

async def _run_analysis(error_log_id: str, log_base_url: str,
                        send_progress: Callable[[str, str], Awaitable[None]],
                        send_token: Callable[[str], Awaitable[None]]) -> dict:
    error_log = await _get_error_log_detail(error_log_id)
    if not error_log:
        raise ValueError("未找到异常日志")

    log_tail = await _download_log_tail(log_base_url, error_log.get("log_path", ""))

    sections = [f"## 日志文件尾部内容\n```\n{log_tail}\n```"] if log_tail else []

    await send_progress("ragflow", "正在检索知识库...")
    refs_result = []
    try:
        search_query = " ".join(filter(None, [
            error_log.get("fail_details", ""), error_log.get("test_item", ""),
            error_log.get("fault_type1", ""), error_log.get("fault_type2", ""), error_log.get("fault_type3", ""),
        ]))
        if search_query.strip():
            result = await ragflow_service.search_knowledge_base(question=search_query, top_k=RAG_TOP_K)
            refs = result.get("references", [])
            if refs:
                seen = {}
                for ref in refs:
                    seen.setdefault(ref.get("doc_name", "未知"), []).append(ref.get("content", ""))
                kb_lines = ["## 知识库参考文档\n从知识库中检索到的相关技术文档（已按文档去重）："]
                for idx, (doc_name, chunks) in enumerate(seen.items(), 1):
                    merged = "\n".join(chunks)
                    kb_lines.append(f"\n[参考 {idx}] 来源: {doc_name}\n    内容: {merged}")
                    refs_result.append({"source": doc_name, "content": merged[:1000]})
                sections.append("\n".join(kb_lines))
            else:
                sections.append("（知识库未检索到匹配内容）")
        else:
            sections.append("（无可用检索条件）")
    except Exception as e:
        logger.warning("知识库检索失败: %s", e)
        sections.append("（知识库检索异常）")

    await send_progress("llm", "正在调用大模型深度诊断...")
    analysis = await llm_service.analyze_with_knowledge_stream(error_log, "\n\n".join(sections), send_token)

    now = datetime.now(timezone.utc).isoformat()
    cache_doc = {
        "error_log_id": error_log_id, "sn": error_log.get("sn", ""), "test_item": error_log.get("test_item", ""),
        **analysis, "knowledge_refs": list({r["source"]: r for r in (analysis.get("knowledge_refs") or refs_result) if r.get("source")}.values()),
        "log_content": log_tail, "created_at": now,
    }
    insert_result = await get_collection("diagnosis_cache").insert_one(cache_doc)

    return _build_cache_response(insert_result, error_log_id, cache_doc["sn"], cache_doc["test_item"], now)


# ── 路由 ──

@router.post("/error-log/{error_log_id}/analyze")
async def analyze_error_log_with_kb(error_log_id: str, current_user: dict = Depends(get_current_user),
                                     log_base_url: str = Query("")):
    cache_col = get_collection("diagnosis_cache")

    cached = await cache_col.find_one({"error_log_id": error_log_id})
    if cached:
        async def _cached_stream():
            yield _sse("done", {"success": True, "data": await _build_cached_response(cached)})
        return StreamingResponse(_cached_stream(), media_type="text/event-stream")

    async def _generate():
        queue: asyncio.Queue = asyncio.Queue()

        async def _runner():
            try:
                result = await _run_analysis(error_log_id, log_base_url,
                                             lambda s, d: queue.put(("progress", {"stage": s, "detail": d})),
                                             lambda t: queue.put(("token", {"text": t})))
                await queue.put(("done", {"success": True, "data": result}))
            except Exception as e:
                msg = str(e) if isinstance(e, ValueError) else f"诊断分析失败: {e}"
                logger.warning(msg) if isinstance(e, ValueError) else logger.exception(msg)
                await queue.put(("error", {"message": msg}))

        task = asyncio.create_task(_runner())
        while True:
            event_type, data = await queue.get()
            yield _sse(event_type, data)
            if event_type in ("done", "error"):
                break
        await task

    return StreamingResponse(_generate(), media_type="text/event-stream")


@router.post("/error-log/{error_log_id}/re-analyze")
async def re_analyze_error_log(error_log_id: str, current_user: dict = Depends(get_current_user),
                                log_base_url: str = Query("")):
    await get_collection("diagnosis_cache").delete_one({"error_log_id": error_log_id})
    return await analyze_error_log_with_kb(error_log_id, current_user, log_base_url)
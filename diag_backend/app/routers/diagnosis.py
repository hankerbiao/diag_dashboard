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
from ..core.factory_config import get_factory_by_id
from ..models.request import (DiagnosisBySNRequest, DiagnosisByErrorLogRequest,
                               DiagnosisFollowUpRequest, SaveSnHistoryRequest, AppendChatRequest)
from ..models.response import (ApiResponse, DiagnosisCacheResponse, DiagnosisResponse,
                               ErrorAnalysisResponse, SnHistoryItem, SnHistoryDetail)
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

async def _gather_sn_data(
    sn: str, factory: str,
    on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None,
) -> tuple[dict, list[dict], list[dict], list[dict], list[dict], str, list[dict]]:
    """收集 SN 诊断所需数据。返回 (device, test_logs, maintenance, all_logs, similar_cases, kb_context, failed_logs)"""
    col = get_collection("sync_remote_test_details")

    async def _progress(s: str, d: str):
        if on_progress:
            await on_progress(s, d)

    await _progress("device", "正在查询设备信息...")
    device = await knowledge_graph.get_device_by_sn(sn)
    if not device:
        exists = await col.find_one({"server_sn": sn})
        if exists:
            device = {"id": "", "sn": sn, "model": "", "factory": factory}
        else:
            raise ValueError("未找到设备信息")

    await _progress("logs", "正在检索测试日志...")
    test_logs = await knowledge_graph.get_device_test_logs(device["id"]) if device["id"] else []
    maintenance = await knowledge_graph.get_device_maintenance_history(device["id"]) if device["id"] else []

    raw_logs = await col.find({"server_sn": sn}).sort("test_time", -1).limit(50).to_list(50)
    detail_logs = []
    failed_logs: list[dict] = []
    for r in raw_logs:
        result = r.get("server_test_result", "")
        is_fail = result and result.upper() not in ("PASS", "OK", "通过", "")
        log_entry = dict(
            id=str(r["_id"]), test_item=r.get("detailed_flow", r.get("big_flow", "")),
            test_time=str(r.get("test_time", "")), fail_details=result,
            fault_type1=r.get("fault_type1", ""), fault_type2=r.get("fault_type2", ""),
            fault_type3=r.get("fault_type3", ""), decision=r.get("decision", ""),
            big_flow=r.get("big_flow", ""), log_path=r.get("log_path", ""),
        )
        detail_logs.append(log_entry)
        if is_fail:
            failed_logs.append(log_entry)

    seen = set()
    all_logs: list[dict] = []
    for log in detail_logs + [dict(
        id=l.get("id", ""), test_item=l.get("test_item", ""),
        test_time=str(l.get("test_time", "")), fail_details=l.get("fail_details", ""),
        log_path=l.get("log_path", ""),
    ) for l in test_logs]:
        key = (log["test_item"], log["test_time"])
        if key not in seen:
            seen.add(key)
            all_logs.append(log)

    await _progress("cases", "正在匹配历史案例...")
    similar_cases = await knowledge_graph.find_similar_cases(
        ",".join([l.get("fail_details", "") for l in test_logs[:5]]))

    # RAGFlow 知识库检索 — 以失败用例为搜索上下文
    await _progress("ragflow", "正在检索知识库...")
    kb_context = ""
    try:
        search_terms = []
        for fl in failed_logs[:5]:
            search_terms.append(fl["test_item"])
            if fl.get("fail_details"):
                search_terms.append(fl["fail_details"])
        # 也从 raw_logs 补充 fault_type
        for r in raw_logs[:10]:
            result = r.get("server_test_result", "")
            if result and result.upper() not in ("PASS", "OK", "通过", ""):
                for ft in ("fault_type1", "fault_type2", "fault_type3"):
                    val = r.get(ft, "")
                    if val:
                        search_terms.append(val)

        query = " ".join(search_terms[:15]) if search_terms else ""
        if query.strip():
            kb_result = await ragflow_service.search_knowledge_base(question=query, top_k=RAG_TOP_K)
            refs = kb_result.get("references", [])
            if refs:
                seen_docs: dict[str, list[str]] = {}
                for ref in refs:
                    seen_docs.setdefault(ref.get("doc_name", "未知"), []).append(ref.get("content", ""))
                kb_lines = ["## 知识库参考文档\n从知识库中检索到的相关技术文档："]
                for idx, (doc_name, chunks) in enumerate(seen_docs.items(), 1):
                    merged = "\n".join(chunks)
                    kb_lines.append(f"\n[参考 {idx}] 来源: {doc_name}\n    内容: {merged[:800]}")
                kb_context = "\n".join(kb_lines)
    except Exception as e:
        logger.warning("SN 诊断知识库检索失败: %s", e)

    return device, test_logs, maintenance, all_logs, similar_cases, kb_context, failed_logs


def _build_sn_response(sn: str, diagnosis: dict, maintenance: list[dict],
                       all_logs: list[dict], similar_cases: list[dict]) -> DiagnosisResponse:
    return DiagnosisResponse(
        sn=sn, category=diagnosis.get("category", "未知"),
        summary=diagnosis.get("summary", ""), confidence=diagnosis.get("confidence", 0.5),
        root_cause_detail=diagnosis.get("root_cause_detail", ""),
        affected_components=diagnosis.get("affected_components", []),
        suggestions=diagnosis.get("suggestions", []),
        preventive_measures=diagnosis.get("preventive_measures", []),
        reference_logs=[],
        maintenance_history=[{"id": m.get("id", ""), "date": m.get("date", ""),
                              "component": m.get("component", ""), "action": m.get("action", "")}
                             for m in maintenance[:5]],
        test_logs=all_logs[:10],
        similar_cases=[dict(
            id=c.get("id", ""), title=c.get("title", ""),
            root_cause=c.get("root_cause", ""), similarity=c.get("similarity", 0.0),
        ) for c in similar_cases],
    )


@router.post("/sn")
async def diagnose_by_sn(request: DiagnosisBySNRequest, current_user: dict = Depends(get_current_user)):
    try:
        device, test_logs, maintenance, all_logs, similar_cases, kb_context, failed_logs = \
            await _gather_sn_data(request.sn, request.factory)
        diagnosis = await llm_service.diagnose_sn(
            request.sn, device, test_logs, maintenance, similar_cases,
            kb_context=kb_context, failed_logs=failed_logs)
        return ApiResponse(success=True, data=_build_sn_response(request.sn, diagnosis, maintenance, all_logs, similar_cases))
    except ValueError as e:
        return ApiResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception("SN 诊断失败")
        return ApiResponse(success=False, error=f"诊断失败: {e}")


@router.post("/sn/follow-up", response_model=ApiResponse)
async def diagnose_sn_follow_up(request: DiagnosisFollowUpRequest, current_user: dict = Depends(get_current_user)):
    try:
        answer = await llm_service.follow_up_question(request.question, request.diagnosis_context)
        return ApiResponse(success=True, data={"answer": answer})
    except Exception as e:
        logger.exception("SN 追问失败")
        return ApiResponse(success=False, error=f"追问失败: {e}")


@router.post("/sn/log-content", response_model=ApiResponse)
async def get_sn_log_content(request: DiagnosisBySNRequest, log_path: str = Query(""),
                              current_user: dict = Depends(get_current_user)):
    """下载 SN 关联的错误日志原文"""
    try:
        factory_info = get_factory_by_id(request.factory)
        log_base_url = factory_info.get("log_base_url", "") if factory_info else ""
        if not log_base_url or not log_path:
            return ApiResponse(success=False, error="日志路径或厂区 log_base_url 未配置")

        content = await _download_log_tail(log_base_url, log_path)
        if not content:
            return ApiResponse(success=False, error="日志内容为空或下载失败")
        return ApiResponse(success=True, data={"content": content})
    except Exception as e:
        logger.exception("日志下载失败")
        return ApiResponse(success=False, error=f"下载失败: {e}")


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
        if url.startswith("ftp://"):
            return await _download_log_tail_ftp(url, tail_lines)
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


async def _download_log_tail_ftp(url: str, tail_lines: int) -> str:
    """通过 FTP 下载日志尾部内容"""
    from urllib.parse import urlparse
    import ftplib
    import io

    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 21
    path = parsed.path or ""

    try:
        loop = asyncio.get_event_loop()
        buf = io.BytesIO()

        def _ftp_download():
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=30)
            ftp.login()  # anonymous
            ftp.retrbinary(f"RETR {path}", buf.write)
            ftp.quit()

        await loop.run_in_executor(None, _ftp_download)
        text = buf.getvalue().decode("utf-8", errors="replace")

        if len(text) > MAX_LOG_BYTES:
            text = text[-MAX_LOG_BYTES:]
        lines = text.splitlines()
        return "\n".join(lines[-tail_lines:] if len(lines) > tail_lines else lines)
    except Exception as e:
        logger.warning("FTP 日志下载失败 [%s]: %s", url, e)
        return ""


def _build_cache_response(cache_doc: dict, log_id: str, sn: str, test_item: str, now: str, doc_id: str) -> dict:
    return DiagnosisCacheResponse(
        id=doc_id, error_log_id=log_id, sn=sn, test_item=test_item,
        root_cause=cache_doc.get("root_cause", ""), evidence=cache_doc.get("evidence", []),
        analysis=cache_doc.get("analysis", ""), repair_suggestions=cache_doc.get("repair_suggestions", []),
        knowledge_refs=cache_doc.get("knowledge_refs", []), log_content=cache_doc.get("log_content", ""),
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

    return _build_cache_response(cache_doc, error_log_id, cache_doc["sn"], cache_doc["test_item"], now, str(insert_result.inserted_id))


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

    async def _runner(send_progress, send_token):
        return await _run_analysis(error_log_id, log_base_url, send_progress, send_token)

    return StreamingResponse(_sse_wrap(_runner, "诊断分析失败"), media_type="text/event-stream")


@router.post("/error-log/{error_log_id}/re-analyze")
async def re_analyze_error_log(error_log_id: str, current_user: dict = Depends(get_current_user),
                                log_base_url: str = Query("")):
    await get_collection("diagnosis_cache").delete_one({"error_log_id": error_log_id})
    return await analyze_error_log_with_kb(error_log_id, current_user, log_base_url)


# ── SSE 通用工具 ──

async def _sse_wrap(runner: Callable[[Callable[[str, str], Awaitable[None]],
                                      Callable[[str], Awaitable[None]]], Awaitable[dict]],
                    on_error_prefix: str = "诊断失败"):
    """统一 SSE 流包装：创建队列 → 启动 runner → 产出 SSE 事件"""
    queue: asyncio.Queue = asyncio.Queue()

    async def _run():
        async def _progress(stage: str, detail: str):
            await queue.put(("progress", {"stage": stage, "detail": detail}))

        async def _token(text: str):
            await queue.put(("token", {"text": text}))

        try:
            result = await asyncio.wait_for(runner(_progress, _token), timeout=600.0)
            await queue.put(("done", {"success": True, "data": result}))
        except asyncio.TimeoutError:
            logger.error("诊断超时（10分钟）")
            await queue.put(("error", {"message": "诊断超时，大模型响应时间过长，请稍后重试"}))
        except Exception as e:
            msg = str(e) if isinstance(e, ValueError) else f"{on_error_prefix}: {e}"
            logger.warning(msg) if isinstance(e, ValueError) else logger.exception(msg)
            await queue.put(("error", {"message": msg}))

    task = asyncio.create_task(_run())
    while True:
        event_type, data = await queue.get()
        yield _sse(event_type, data)
        if event_type in ("done", "error"):
            break
    await task


# ── SN 诊断 SSE ──

@router.post("/sn/analyze")
async def diagnose_sn_stream(request: DiagnosisBySNRequest, current_user: dict = Depends(get_current_user)):
    async def _runner(send_progress, send_token):
        device, test_logs, maintenance, all_logs, similar_cases, kb_context, failed_logs = \
            await _gather_sn_data(request.sn, request.factory, on_progress=send_progress)

        await send_progress("llm", "正在调用大模型深度诊断...")
        diagnosis = await llm_service.diagnose_sn_stream(
            request.sn, device, test_logs, maintenance, similar_cases, send_token,
            kb_context=kb_context, failed_logs=failed_logs)

        return _build_sn_response(request.sn, diagnosis, maintenance, all_logs, similar_cases).model_dump()

    return StreamingResponse(_sse_wrap(_runner), media_type="text/event-stream")


# ── SN 诊断历史记录 ──


@router.post("/sn/save-history", response_model=ApiResponse)
async def save_sn_history(request: SaveSnHistoryRequest, current_user: dict = Depends(get_current_user)):
    """保存 SN 诊断结果到历史记录"""
    try:
        result = request.diagnosis_result
        doc = {
            "sn": request.sn,
            "factory": request.factory,
            "category": result.get("category", ""),
            "confidence": result.get("confidence", 0.0),
            "summary": result.get("summary", ""),
            "diagnosis_result": result,
            "chat_messages": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        col = get_collection("diagnosis_sn_history")
        insert_result = await col.insert_one(doc)
        return ApiResponse(success=True, data={"id": str(insert_result.inserted_id)})
    except Exception as e:
        logger.exception("保存诊断历史失败")
        return ApiResponse(success=False, error=f"保存失败: {e}")


@router.put("/sn/history/{history_id}/chat", response_model=ApiResponse)
async def append_chat_message(history_id: str, request: AppendChatRequest,
                               current_user: dict = Depends(get_current_user)):
    """追加对话消息到历史记录"""
    try:
        col = get_collection("diagnosis_sn_history")
        result = await col.update_one(
            {"_id": ObjectId(history_id)},
            {"$push": {"chat_messages": {"role": request.role, "content": request.content}},
             "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        if result.matched_count == 0:
            return ApiResponse(success=False, error="历史记录不存在")
        return ApiResponse(success=True)
    except Exception as e:
        logger.exception("追加对话失败")
        return ApiResponse(success=False, error=f"追加失败: {e}")


@router.get("/sn/history", response_model=ApiResponse)
async def list_sn_history(sn: str = Query(""), factory: str = Query(""),
                           page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
                           current_user: dict = Depends(get_current_user)):
    """查询 SN 诊断历史记录列表"""
    try:
        col = get_collection("diagnosis_sn_history")
        query = {}
        if sn:
            query["sn"] = sn
        if factory:
            query["factory"] = factory

        total = await col.count_documents(query)
        docs = await col.find(query, {"diagnosis_result": 0}).sort("created_at", -1) \
            .skip((page - 1) * limit).limit(limit).to_list(limit)

        items = [SnHistoryItem(
            id=str(d["_id"]), sn=d["sn"], factory=d.get("factory", ""),
            category=d.get("category", ""), confidence=d.get("confidence", 0.0),
            summary=d.get("summary", ""), created_at=d["created_at"],
        ) for d in docs]

        return ApiResponse(success=True, data={"items": [i.model_dump() for i in items], "total": total,
                                                "page": page, "limit": limit})
    except Exception as e:
        logger.exception("查询诊断历史失败")
        return ApiResponse(success=False, error=f"查询失败: {e}")


@router.get("/sn/history/{history_id}", response_model=ApiResponse)
async def get_sn_history_detail(history_id: str, current_user: dict = Depends(get_current_user)):
    """查询单条诊断历史完整记录（含对话）"""
    try:
        col = get_collection("diagnosis_sn_history")
        doc = await col.find_one({"_id": ObjectId(history_id)})
        if not doc:
            return ApiResponse(success=False, error="历史记录不存在")

        return ApiResponse(success=True, data=SnHistoryDetail(
            id=str(doc["_id"]), sn=doc["sn"], factory=doc.get("factory", ""),
            diagnosis_result=doc.get("diagnosis_result", {}),
            chat_messages=doc.get("chat_messages", []),
            created_at=doc["created_at"], updated_at=doc.get("updated_at", doc["created_at"]),
        ).model_dump())
    except Exception as e:
        logger.exception("查询诊断历史详情失败")
        return ApiResponse(success=False, error=f"查询失败: {e}")

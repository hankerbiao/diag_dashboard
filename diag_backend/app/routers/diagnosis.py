import asyncio
import json
import logging
from ..core.utils import (
    utc_now_iso,
    is_test_failed,
    is_sims_record_failed,
    validate_log_path,
    parse_object_id,
    build_log_download_url,
)
from typing import Awaitable, Callable, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..core.auth import get_current_user
from ..core.factory_config import get_factory_by_id, load_factories_from_yaml
from ..core.mongodb import get_collection
from ..models.request import (
    DiagnosisBySNRequest,
    DiagnosisFollowUpRequest,
    SaveSnHistoryRequest,
    AppendChatRequest,
    ErrorLogAnalyzeContext,
    DiagnosisFeedbackRequest,
)
from ..models.api import ApiResponse
from ..models.diagnosis import (
    DiagnosisCacheResponse,
    DiagnosisResponse,
    ErrorAnalysisResponse,
    SnHistoryItem,
    SnHistoryDetail,
)
from ..services.llm_service import llm_service
from ..services.knowledge_graph import knowledge_graph
from ..services.mes_direct_service import MESDirectService, MESRequestError
from ..services import ragflow_service

logger = logging.getLogger(__name__)

MAX_LOG_BYTES = 2 * 1024 * 1024
LOG_TAIL_LINES = 50
RAG_TOP_K = 10

# LLM 上下文窗口安全限制（为模型最大上下文留出 4096 token 余量给 system prompt 和输出）
# 例如模型 32K → MAX_PROMPT_TOKENS ≈ 28K
MAX_PROMPT_TOKENS = 28_000

router = APIRouter(prefix="/diagnosis", tags=["诊断"])


# ── SSE 工具 ──


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── 通用诊断 ──


async def _gather_sn_data(
    sn: str,
    factory: str,
    on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None,
) -> tuple[dict, list[dict], list[dict], list[dict], list[dict], str, list[dict]]:
    """收集 SN 诊断所需数据。返回 (device, llm_logs, maintenance, all_logs, similar_cases, kb_context, failed_logs)"""
    async def _progress(s: str, d: str):
        if on_progress:
            await on_progress(s, d)

    factory_cfg = get_factory_by_id(factory)
    if not factory_cfg:
        raise ValueError(f"厂区不存在: {factory}")
    factory_label = factory_cfg["name"]

    await _progress("device", "正在查询设备信息...")
    device = await knowledge_graph.get_device_by_sn(sn)

    await _progress("sims", f"正在向 SIMS（{factory_label}）实时查询测试数据...")
    sims_path = "/stepsmanagement/resultInfo/queryTestList.action"
    sims_params = {"start": 0, "limit": 50, "serverSN": sn, "customerID": ""}
    async with MESDirectService() as mes:
        try:
            result = await mes.get_test_details(factory, server_sn=sn, limit=50)
            raw_logs = result["items"]
        except MESRequestError as e:
            debug = e.debug
            logger.warning(
                "SIMS 查询失败 [%s] sn=%s factory=%s url=%s params=%s error=%s",
                factory_label,
                sn,
                factory,
                debug.get("url"),
                debug.get("params"),
                e,
            )
            logger.debug(
                "SIMS 查询请求详情: %s",
                json.dumps(debug, ensure_ascii=False, default=str),
            )
            raise ValueError(
                f"SIMS 查询失败 [{factory_label}]: 请确认 SN 正确且厂区 SIMS 可达。"
            ) from e
        except Exception as e:
            debug = mes._request_debug(factory, sims_path, sims_params)
            logger.warning(
                "SIMS 查询异常 [%s] sn=%s factory=%s url=%s params=%s error=%s",
                factory_label,
                sn,
                factory,
                debug.get("url"),
                debug.get("params"),
                e,
            )
            logger.debug(
                "SIMS 查询请求详情: %s",
                json.dumps(debug, ensure_ascii=False, default=str),
            )
            raise ValueError(
                f"SIMS 查询失败 [{factory_label}]: 请确认 SN 正确且厂区 SIMS 可达。"
            ) from e

        if not raw_logs:
            raise ValueError(
                f"SIMS 未查询到 SN「{sn}」在「{factory_label}」的测试记录（0 条），"
                f"请确认 SN 与厂区选择正确，且该设备已在 SIMS 中参与测试。"
            )

        if not device:
            server = await mes.get_server(factory, sn)
            device = {
                "id": "",
                "sn": sn,
                "model": server.model if server else "",
                "factory": factory,
            }

    maintenance = (
        await knowledge_graph.get_device_maintenance_history(device["id"])
        if device.get("id")
        else []
    )
    mongo_test_logs = (
        await knowledge_graph.get_device_test_logs(device["id"]) if device.get("id") else []
    )

    detail_logs: list[dict] = []
    failed_logs: list[dict] = []
    for idx, r in enumerate(raw_logs):
        result_status = (r.get("server_test_result") or r.get("decision") or "").strip()
        log_entry = dict(
            id=str(r.get("_id", f"mes_{factory}_{sn}_{idx}")),
            test_item=r.get("detailed_flow", r.get("big_flow", "")),
            test_time=str(r.get("test_time", "")),
            fail_details=result_status,
            fault_type1=r.get("fault_type1", ""),
            fault_type2=r.get("fault_type2", ""),
            fault_type3=r.get("fault_type3", ""),
            decision=r.get("decision", ""),
            big_flow=r.get("big_flow", ""),
            log_path=r.get("log_path", ""),
        )
        detail_logs.append(log_entry)
        if is_sims_record_failed(r):
            failed_logs.append(log_entry)

    seen = set()
    all_logs: list[dict] = []
    for log in detail_logs + [
        dict(
            id=tl.get("id", ""),
            test_item=tl.get("test_item", ""),
            test_time=str(tl.get("test_time", "")),
            fail_details=tl.get("fail_details", ""),
            log_path=tl.get("log_path", ""),
        )
        for tl in mongo_test_logs
    ]:
        key = (log["test_item"], log["test_time"], log.get("fail_details", ""))
        if key not in seen:
            seen.add(key)
            all_logs.append(log)

    llm_logs = all_logs

    log_file_context = await _download_failed_item_logs(
        log_base_url=factory_cfg.get("log_base_url", ""),
        failed_logs=failed_logs,
        factory_label=factory_label,
        ftp_user=factory_cfg.get("log_ftp_user"),
        ftp_password=factory_cfg.get("log_ftp_password"),
        on_progress=_progress if on_progress else None,
    )

    if failed_logs:
        await _progress("cases", f"正在匹配历史案例（{len(failed_logs)} 条失败项）...")
    else:
        await _progress("cases", "未发现失败用例，将基于全部测试记录分析...")

    case_terms: list[str] = []
    for fl in failed_logs[:5]:
        if fl.get("test_item"):
            case_terms.append(fl["test_item"])
        if fl.get("fail_details"):
            case_terms.append(fl["fail_details"])
        for ft in ("fault_type1", "fault_type2", "fault_type3"):
            if fl.get(ft):
                case_terms.append(fl[ft])
    search_text = " ".join(case_terms).strip()
    similar_cases: list[dict] = []
    if search_text:
        try:
            similar_cases = await knowledge_graph.find_similar_cases(search_text)
        except Exception as e:
            logger.warning("相似案例检索失败", extra={"sn": sn, "error": str(e)})

    # RAGFlow 知识库检索 — 以失败用例为搜索上下文
    await _progress("ragflow", "正在检索知识库...")
    kb_context = ""
    try:
        search_terms = list(case_terms)
        for r in raw_logs[:10]:
            if is_sims_record_failed(r):
                for ft in ("fault_type1", "fault_type2", "fault_type3"):
                    val = r.get(ft, "")
                    if val:
                        search_terms.append(val)

        query = " ".join(search_terms[:15]) if search_terms else ""
        logger.debug("知识库检索 _gather_sn_data", extra={"sn": sn, "query": query[:200]})
        if query.strip():
            kb_result = await ragflow_service.search_knowledge_base(
                question=query, top_k=RAG_TOP_K
            )
            refs = kb_result.get("references", [])
            logger.debug("知识库检索结果", extra={"sn": sn, "refs_count": len(refs)})
            if refs:
                seen_docs: dict[str, list[str]] = {}
                for ref in refs:
                    seen_docs.setdefault(ref.get("doc_name", "未知"), []).append(
                        ref.get("content", "")
                    )
                kb_lines = ["## 知识库参考文档\n从知识库中检索到的相关技术文档："]
                for idx, (doc_name, chunks) in enumerate(seen_docs.items(), 1):
                    merged = "\n".join(chunks)
                    kb_lines.append(
                        f"\n[参考 {idx}] 来源: {doc_name}\n    内容: {merged[:800]}"
                    )
                kb_context = "\n".join(kb_lines)
    except Exception as e:
        logger.warning("知识库检索失败", extra={"sn": sn, "query": query[:200] if query else "", "error": str(e), "error_type": type(e).__name__})

    if log_file_context:
        kb_context = f"{kb_context}\n\n{log_file_context}" if kb_context else log_file_context

    return (
        device,
        llm_logs,
        maintenance,
        all_logs,
        similar_cases,
        kb_context,
        failed_logs,
    )


def _map_test_log_items(logs: list[dict]) -> list:
    return [
        {
            "id": str(log.get("id", "")),
            "test_item": log.get("test_item", ""),
            "test_time": str(log.get("test_time", "")),
            "fail_details": log.get("fail_details", ""),
            "fault_type1": log.get("fault_type1", ""),
            "fault_type2": log.get("fault_type2", ""),
            "fault_type3": log.get("fault_type3", ""),
            "decision": log.get("decision", ""),
            "big_flow": log.get("big_flow", ""),
            "log_path": log.get("log_path", ""),
        }
        for log in logs
    ]


def _build_sn_response(
    sn: str,
    diagnosis: dict,
    maintenance: list[dict],
    all_logs: list[dict],
    similar_cases: list[dict],
    failed_logs: Optional[list[dict]] = None,
) -> DiagnosisResponse:
    return DiagnosisResponse(
        sn=sn,
        category=diagnosis.get("category", "未知"),
        summary=diagnosis.get("summary", ""),
        confidence=diagnosis.get("confidence", 0.5),
        root_cause_detail=diagnosis.get("root_cause_detail", ""),
        affected_components=diagnosis.get("affected_components", []),
        suggestions=diagnosis.get("suggestions", []),
        preventive_measures=diagnosis.get("preventive_measures", []),
        reference_logs=[],
        maintenance_history=[
            {
                "id": m.get("id", ""),
                "date": m.get("date", ""),
                "component": m.get("component", ""),
                "action": m.get("action", ""),
            }
            for m in maintenance[:5]
        ],
        test_logs=_map_test_log_items(all_logs[:10]),
        failed_test_logs=_map_test_log_items((failed_logs or [])[:20]),
        similar_cases=[
            dict(
                id=c.get("id", ""),
                title=c.get("title") or c.get("root_cause", ""),
                root_cause=c.get("root_cause", ""),
                similarity=c.get("similarity", 0.0),
            )
            for c in similar_cases
        ],
    )


@router.post("/sn")
async def diagnose_by_sn(
    request: DiagnosisBySNRequest, current_user: dict = Depends(get_current_user)
):
    try:
        (
            device,
            llm_logs,
            maintenance,
            all_logs,
            similar_cases,
            kb_context,
            failed_logs,
        ) = await _gather_sn_data(request.sn, request.factory)
        diagnosis = await llm_service.diagnose_sn(
            request.sn,
            device,
            llm_logs,
            maintenance,
            similar_cases,
            kb_context=kb_context,
            failed_logs=failed_logs,
        )
        logger.info(
            "SN 诊断完成",
            extra={
                "sn": request.sn,
                "factory": request.factory,
                "test_logs_count": len(llm_logs),
                "similar_cases_count": len(similar_cases),
                "kb_context_length": len(kb_context) if kb_context else 0,
            },
        )
        return ApiResponse(
            success=True,
            data=_build_sn_response(
                request.sn, diagnosis, maintenance, all_logs, similar_cases, failed_logs
            ),
        )
    except ValueError as e:
        logger.warning(
            "SN 诊断参数错误",
            extra={"sn": request.sn, "factory": request.factory, "error": str(e)},
        )
        return ApiResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception(
            "SN 诊断失败", extra={"sn": request.sn, "factory": request.factory}
        )
        return ApiResponse(success=False, error=f"诊断失败: {e}")


@router.post("/sn/follow-up", response_model=ApiResponse)
async def diagnose_sn_follow_up(
    request: DiagnosisFollowUpRequest, current_user: dict = Depends(get_current_user)
):
    try:
        answer = await llm_service.follow_up_question(
            request.question, request.diagnosis_context
        )
        logger.info("SN 追问完成", extra={"question_length": len(request.question)})
        return ApiResponse(success=True, data={"answer": answer})
    except Exception as e:
        logger.exception(
            "SN 追问失败", extra={"question_length": len(request.question)}
        )
        return ApiResponse(success=False, error=f"追问失败: {e}")


@router.post("/sn/log-content", response_model=ApiResponse)
async def get_sn_log_content(
    request: DiagnosisBySNRequest,
    log_path: str = Query(""),
    current_user: dict = Depends(get_current_user),
):
    """下载 SN 关联的错误日志原文"""
    try:
        safe_path = validate_log_path(log_path)
        factory_info = get_factory_by_id(request.factory)
        if not factory_info:
            return ApiResponse(success=False, error=f"厂区不存在: {request.factory}")
        log_base_url = factory_info.get("log_base_url", "")
        if not log_base_url:
            return ApiResponse(success=False, error="厂区 log_base_url 未配置")

        content, dl_error = await _download_log_tail(
            log_base_url,
            safe_path,
            ftp_user=factory_info.get("log_ftp_user"),
            ftp_password=factory_info.get("log_ftp_password"),
        )
        if dl_error:
            return ApiResponse(success=False, error=dl_error)
        if not content:
            return ApiResponse(success=False, error="日志内容为空")
        return ApiResponse(success=True, data={"content": content})
    except ValueError as e:
        return ApiResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception(
            "日志下载失败",
            extra={"sn": request.sn, "log_path": log_path, "factory": request.factory},
        )
        return ApiResponse(success=False, error=f"下载失败: {e}")


@router.post("/error-log/{error_log_id}", response_model=ApiResponse)
async def analyze_error_log(
    error_log_id: str, current_user: dict = Depends(get_current_user)
):
    try:
        error_log = await knowledge_graph.get_error_log_by_id(error_log_id)
        if not error_log:
            return ApiResponse(success=False, error="未找到异常日志")

        similar_cases = await knowledge_graph.find_similar_cases(
            error_log.get("fail_details", "")
        )
        analysis = await llm_service.analyze_error(error_log, similar_cases)

        logger.info(
            "异常日志分析完成",
            extra={
                "error_log_id": error_log_id,
                "similar_cases_count": len(similar_cases),
            },
        )
        return ApiResponse(
            success=True,
            data=ErrorAnalysisResponse(
                error_log=error_log,
                analysis=analysis.get("analysis", ""),
                root_cause=analysis.get("root_cause", ""),
                repair_suggestions=analysis.get("repair_suggestions", []),
                similar_cases=similar_cases,
            ),
        )
    except Exception as e:
        logger.exception("异常日志分析失败", extra={"error_log_id": error_log_id})
        return ApiResponse(success=False, error=f"分析失败: {e}")


# ── 辅助函数 ──


def _detail_from_analyze_context(error_log_id: str, ctx: ErrorLogAnalyzeContext) -> dict:
    return {
        "id": error_log_id,
        "sn": ctx.server_sn,
        "factory_id": ctx.factory_id,
        "test_item": ctx.test_item,
        "test_time": ctx.test_time,
        "fail_details": ctx.fail_details,
        "fault_type1": ctx.fault_type1,
        "fault_type2": ctx.fault_type2,
        "fault_type3": ctx.fault_type3,
        "log_path": ctx.log_path,
    }


def _detail_from_mes_item(item: dict, record_id: str) -> dict:
    return {
        "id": record_id,
        "sn": item.get("server_sn", ""),
        "factory_id": item.get("factory_id", ""),
        "test_item": item.get("detailed_flow", item.get("big_flow", "")),
        "test_time": item.get("test_time", ""),
        "fail_details": item.get("server_test_result", ""),
        "fault_type1": item.get("fault_type1", ""),
        "fault_type2": item.get("fault_type2", ""),
        "fault_type3": item.get("fault_type3", ""),
        "log_path": item.get("log_path", ""),
    }


def _parse_mes_client_detail_id(error_log_id: str) -> Optional[dict]:
    """解析 MES 实时详情合成 ID：{factory_id}_{server_sn}_{test_time}_{idx}"""
    import re

    for factory in load_factories_from_yaml():
        factory_id = factory.get("factory_id") or ""
        prefix = f"{factory_id}_"
        if not error_log_id.startswith(prefix):
            continue
        rest = error_log_id[len(prefix) :]
        if "_" not in rest:
            continue
        body, idx_s = rest.rsplit("_", 1)
        if not idx_s.isdigit():
            continue
        year_match = re.search(r"_((?:19|20)\d{2}[-/])", body)
        if year_match:
            server_sn = body[: year_match.start()]
            test_time = body[year_match.start() + 1 :]
        else:
            server_sn, _, test_time = body.partition("_")
            if not test_time:
                continue
        return {
            "factory_id": factory_id,
            "server_sn": server_sn,
            "test_time": test_time,
            "idx": int(idx_s),
        }
    return None


def _normalize_test_time(value: object) -> str:
    """统一测试时间字符串，便于 MES 明细匹配。"""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return text.replace("T", " ")[:19]


async def _lookup_test_detail_from_mes(parsed: dict, record_id: str) -> Optional[dict]:
    async with MESDirectService() as mes:
        result = await mes.get_test_details(
            parsed["factory_id"], parsed["server_sn"], limit=500
        )
    items = result.get("items") or []
    target_time = _normalize_test_time(parsed.get("test_time", ""))
    for item in items:
        if _normalize_test_time(item.get("test_time", "")) == target_time:
            return _detail_from_mes_item(item, record_id)
    idx = parsed.get("idx", 0)
    if 0 <= idx < len(items):
        return _detail_from_mes_item(items[idx], record_id)
    return None


async def _get_error_log_detail(
    error_log_id: str,
    context: Optional[ErrorLogAnalyzeContext] = None,
) -> Optional[dict]:
    if context and context.server_sn and context.factory_id:
        return _detail_from_analyze_context(error_log_id, context)

    # 尝试通过 ID 模式从 MES 实时查询
    parsed = _parse_mes_client_detail_id(error_log_id)
    if parsed:
        try:
            mes_detail = await _lookup_test_detail_from_mes(parsed, error_log_id)
            if mes_detail:
                return mes_detail
        except Exception as e:
            logger.warning(
                "MES 测试明细回查失败",
                extra={
                    "error_log_id": error_log_id,
                    "factory_id": parsed.get("factory_id"),
                    "server_sn": parsed.get("server_sn"),
                    "error": str(e),
                },
            )

    return await knowledge_graph.get_error_log_by_id(error_log_id)


def _resolve_log_download_config(
    log_base_url_query: str,
    factory_id: str = "",
) -> tuple[str, Optional[str], Optional[str]]:
    """解析日志下载地址与 FTP 凭据（查询参数优先，否则用厂区 YAML）。"""
    factory_info = get_factory_by_id(factory_id) if factory_id else None
    base_url = (log_base_url_query or "").strip() or (
        (factory_info or {}).get("log_base_url") or ""
    )
    if not factory_info:
        return base_url, None, None
    return (
        base_url,
        factory_info.get("log_ftp_user"),
        factory_info.get("log_ftp_password"),
    )


async def _download_failed_item_logs(
    *,
    log_base_url: str,
    failed_logs: list[dict],
    factory_label: str,
    ftp_user: Optional[str] = None,
    ftp_password: Optional[str] = None,
    on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None,
    max_files: int = 5,
) -> str:
    """下载失败项原文日志；若存在 log_path 但全部失败则中止 SN 诊断。"""
    with_path = [fl for fl in failed_logs if (fl.get("log_path") or "").strip()]
    if not with_path:
        return ""

    if not log_base_url:
        raise ValueError(
            f"厂区「{factory_label}」未配置 log_base_url，无法下载失败项原文日志，已中止诊断。"
        )

    if on_progress:
        await on_progress(
            "logfiles",
            f"正在下载失败项原文日志（最多 {min(len(with_path), max_files)} 个）...",
        )

    blocks: list[str] = []
    errors: list[str] = []

    for fl in with_path[:max_files]:
        log_path = (fl.get("log_path") or "").strip()
        content, dl_error = await _download_log_tail(
            log_base_url,
            log_path,
            ftp_user=ftp_user,
            ftp_password=ftp_password,
        )
        if dl_error:
            errors.append(f"{fl.get('test_item', log_path)}: {dl_error}")
            continue
        if not content.strip():
            errors.append(f"{fl.get('test_item', log_path)}: 日志内容为空")
            continue
        blocks.append(
            f"### [{fl.get('test_time', '')}] {fl.get('test_item', '')}\n"
            f"路径: {log_path}\n```\n{content}\n```"
        )

    if not blocks:
        detail = "；".join(errors[:3])
        if len(errors) > 3:
            detail += f" … 共 {len(errors)} 条失败"
        raise ValueError(f"失败项原文日志全部下载失败，已中止 AI 诊断: {detail}")

    if on_progress:
        msg = f"已下载 {len(blocks)} 份失败项原文日志"
        if errors:
            msg += f"（{len(errors)} 条下载失败已跳过）"
        await on_progress("logfiles", msg)

    return "\n\n## 失败项原文日志（SIMS log_path）\n" + "\n\n".join(blocks)


async def _download_log_tail(
    log_base_url: str,
    log_path: str,
    tail_lines: int = LOG_TAIL_LINES,
    *,
    ftp_user: Optional[str] = None,
    ftp_password: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """下载日志尾部。返回 (content, error_message)，成功时 error_message 为 None。"""
    if not log_base_url or not log_path:
        return "", "log_base_url 或 log_path 为空"
    url = build_log_download_url(log_base_url, log_path)
    if not url:
        return "", "log_base_url 或 log_path 为空"
    logger.debug(
        "日志下载 URL log_base_url=%s log_path=%s -> %s",
        log_base_url,
        log_path,
        url,
    )
    try:
        if url.startswith("ftp://"):
            return await _download_log_tail_ftp(
                url,
                tail_lines,
                ftp_user=ftp_user,
                ftp_password=ftp_password,
            )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text

            if url.endswith(".html"):
                try:
                    from lxml import html as lxml_html

                    tree = lxml_html.fromstring(text)
                    for tag in ("script", "style"):
                        for elem in list(tree.iter(tag)):
                            elem.drop_tree()
                    lines = [
                        ln for ln in tree.text_content().strip().splitlines() if ln.strip()
                    ]
                    return "\n".join(lines), None
                except Exception as e:
                    logger.warning(
                        "HTML 解析失败 url=%s error_type=%s error=%s",
                        url,
                        type(e).__name__,
                        e,
                    )

            if len(text) > MAX_LOG_BYTES:
                text = text[-MAX_LOG_BYTES:]
            lines = text.splitlines()
            return "\n".join(lines[-tail_lines:] if len(lines) > tail_lines else lines), None
    except httpx.HTTPStatusError as e:
        detail = (
            f"HTTP 日志下载失败: {e.response.status_code} {e.response.reason_phrase} "
            f"url={url}"
        )
        logger.warning("%s body_preview=%s", detail, (e.response.text or "")[:200])
        return "", detail
    except httpx.RequestError as e:
        detail = f"HTTP 日志下载网络错误 url={url} error={type(e).__name__}: {e}"
        logger.warning(detail)
        return "", detail
    except Exception as e:
        detail = f"日志下载失败 url={url} error={type(e).__name__}: {e}"
        logger.warning(detail)
        return "", detail


def _describe_ftp_error(
    e: Exception,
    *,
    host: str,
    port: int,
    path: str,
    auth_user: str,
    used_anonymous: bool,
) -> str:
    """将 FTP 异常转为可排查的说明（不含密码）。"""
    import ftplib

    parts = [
        f"FTP 日志下载失败",
        f"host={host}:{port}",
        f"path={path or '/'}",
        f"user={auth_user or 'anonymous'}",
        f"auth={'anonymous' if used_anonymous else 'credentials'}",
        f"error_type={type(e).__name__}",
        f"error={e}",
    ]
    if isinstance(e, ftplib.error_perm):
        reply = e.args[0] if e.args else ""
        parts.append(f"ftp_reply={reply}")
        if "530" in str(reply) or "Login" in str(reply):
            parts.append(
                "hint=登录被拒绝，FTP 可能禁止匿名访问，请在厂区配置 log_ftp_user/log_ftp_password"
            )
        elif "550" in str(reply):
            parts.append("hint=文件不存在或无读取权限，请核对 log_path 与 FTP 目录")
    elif isinstance(e, ftplib.error_temp):
        parts.append(f"ftp_reply={e.args[0] if e.args else ''}")
    elif isinstance(e, (TimeoutError, OSError)):
        parts.append("hint=连接超时或网络不可达，请确认后端能访问 FTP 主机与 21 端口")
    return " | ".join(parts)


def _ftp_has_explicit_credentials(
    url: str,
    ftp_user: Optional[str],
    ftp_password: Optional[str],
) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.username:
        return True
    return bool(ftp_user or ftp_password)


def _tail_text(raw: bytes, tail_lines: int) -> str:
    text = raw.decode("utf-8", errors="replace")
    if len(text) > MAX_LOG_BYTES:
        text = text[-MAX_LOG_BYTES:]
    lines = text.splitlines()
    return "\n".join(lines[-tail_lines:] if len(lines) > tail_lines else lines)


async def _download_log_tail_ftp_urlopen(url: str, tail_lines: int) -> tuple[str, Optional[str]]:
    """无凭据 FTP：与 download_ftp.py 一致，使用 urllib 直接拉取完整 URL。"""
    import urllib.request

    def _fetch() -> bytes:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()

    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, _fetch)
        content = _tail_text(raw, tail_lines)
        logger.debug("FTP urllib 下载成功 url=%s bytes=%s", url, len(raw))
        return content, None
    except Exception as e:
        detail = f"FTP 日志下载失败 url={url} error={type(e).__name__}: {e}"
        logger.warning(detail)
        return "", detail


async def _download_log_tail_ftp(
    url: str,
    tail_lines: int,
    *,
    ftp_user: Optional[str] = None,
    ftp_password: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """通过 FTP 下载日志尾部。无厂区凭据时优先 urllib；有凭据时用 ftplib。"""
    from urllib.parse import urlparse, unquote
    import ftplib
    import io

    if not _ftp_has_explicit_credentials(url, ftp_user, ftp_password):
        return await _download_log_tail_ftp_urlopen(url, tail_lines)

    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 21
    path = unquote(parsed.path or "")

    auth_user = unquote(parsed.username) if parsed.username else (ftp_user or "anonymous")
    auth_password = (
        unquote(parsed.password)
        if parsed.password is not None
        else (ftp_password if ftp_password is not None else "")
    )
    used_anonymous = auth_user in ("anonymous", "") and not auth_password
    if auth_user in ("", "anonymous"):
        auth_user = "anonymous"

    logger.debug(
        "FTP ftplib 下载开始 host=%s port=%s path=%s user=%s anonymous=%s",
        host,
        port,
        path,
        auth_user,
        used_anonymous,
    )

    try:
        loop = asyncio.get_event_loop()
        buf = io.BytesIO()

        def _ftp_download():
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=30)
            ftp.login(auth_user, auth_password)
            ftp.retrbinary(f"RETR {path}", buf.write)
            ftp.quit()

        await loop.run_in_executor(None, _ftp_download)
        content = _tail_text(buf.getvalue(), tail_lines)
        logger.debug(
            "FTP ftplib 下载成功 host=%s path=%s bytes=%s",
            host,
            path,
            len(buf.getvalue()),
        )
        return content, None
    except Exception as e:
        detail = _describe_ftp_error(
            e,
            host=host,
            port=port,
            path=path,
            auth_user=auth_user,
            used_anonymous=used_anonymous,
        )
        logger.warning(detail)
        return "", detail


def _build_cache_response(
    cache_doc: dict, log_id: str, sn: str, test_item: str, now: str, doc_id: str
) -> dict:
    return DiagnosisCacheResponse(
        id=doc_id,
        error_log_id=log_id,
        sn=sn,
        test_item=test_item,
        root_cause=cache_doc.get("root_cause", ""),
        evidence=cache_doc.get("evidence", []),
        analysis=cache_doc.get("analysis", ""),
        repair_suggestions=cache_doc.get("repair_suggestions", []),
        knowledge_refs=cache_doc.get("knowledge_refs", []),
        log_content=cache_doc.get("log_content", ""),
        created_at=now,
        is_cached=False,
    ).model_dump()


async def _build_cached_response(cached: dict) -> dict:
    return DiagnosisCacheResponse(
        id=str(cached["_id"]),
        error_log_id=cached["error_log_id"],
        sn=cached["sn"],
        test_item=cached["test_item"],
        root_cause=cached["root_cause"],
        evidence=cached.get("evidence", []),
        analysis=cached["analysis"],
        repair_suggestions=cached["repair_suggestions"],
        knowledge_refs=cached.get("knowledge_refs", []),
        log_content=cached.get("log_content", ""),
        created_at=cached["created_at"],
        is_cached=True,
    ).model_dump()


# ── 核心诊断逻辑 ──


def _estimate_tokens(text: str) -> int:
    """估算文本的 token 数量（中文 ~1.5 字/token，英文 ~4 字/token）"""
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other = len(text) - chinese
    return int(chinese * 1.5 + other * 0.25) + 1


def _truncate_to_budget(text: str, budget: int, label: str = "内容") -> str:
    """按 token 预算截断文本，保留头部和尾部关键信息"""
    estimated = _estimate_tokens(text)
    if estimated <= budget:
        return text
    avg_bytes_per_token = len(text.encode("utf-8")) / max(estimated, 1)
    target_chars = int(budget * avg_bytes_per_token * 0.9)
    if target_chars >= len(text):
        return text
    # 保留尾巴（日志尾部信息更重要）
    tail_chars = min(target_chars, len(text))
    truncated = text[-tail_chars:]
    logger.info(
        "%s 超出 token 预算: estimated=%d budget=%d original_len=%d truncated_len=%d",
        label, estimated, budget, len(text), len(truncated),
    )
    return truncated


async def _run_analysis(
    error_log_id: str,
    log_base_url: str,
    send_progress: Callable[[str, str], Awaitable[None]],
    send_token: Callable[[str], Awaitable[None]],
    *,
    context: Optional[ErrorLogAnalyzeContext] = None,
) -> dict:
    error_log = await _get_error_log_detail(error_log_id, context)
    if not error_log:
        if context and (context.server_sn or context.log_path):
            logger.debug(
                "异常日志未找到，使用前端上下文数据兜底",
                extra={
                    "error_log_id": error_log_id,
                    "server_sn": context.server_sn or "",
                    "has_log_path": bool(context.log_path),
                },
            )
            error_log = {
                "id": error_log_id,
                "sn": context.server_sn or "",
                "factory_id": context.factory_id or "",
                "test_item": context.test_item,
                "test_time": context.test_time,
                "fail_details": context.fail_details,
                "fault_type1": context.fault_type1,
                "fault_type2": context.fault_type2,
                "fault_type3": context.fault_type3,
                "log_path": context.log_path,
            }
        else:
            raise ValueError("未找到异常日志")

    log_path = (error_log.get("log_path") or "").strip()
    resolved_url, ftp_user, ftp_password = _resolve_log_download_config(
        log_base_url,
        error_log.get("factory_id", ""),
    )
    log_tail = ""
    sections: list[str] = []

    if log_path:
        await send_progress("download", "正在下载日志文件...")
        if not resolved_url:
            raise ValueError(
                "该记录有日志路径但厂区 log_base_url 未配置，已中止 AI 诊断。"
            )
        log_tail, dl_error = await _download_log_tail(
            resolved_url,
            log_path,
            ftp_user=ftp_user,
            ftp_password=ftp_password,
        )
        if dl_error:
            raise ValueError(f"日志下载失败，已中止 AI 诊断: {dl_error}")
        if not log_tail.strip():
            raise ValueError("日志下载成功但内容为空，已中止 AI 诊断。")
        await send_progress("download", "日志下载完成")
        sections.append(f"## 日志文件尾部内容\n```\n{log_tail}\n```")
    else:
        await send_progress("download", "无 log_path，跳过原文日志下载")

    await send_progress("ragflow", "正在检索知识库...")
    refs_result = []
    try:
        search_query = " ".join(
            filter(
                None,
                [
                    error_log.get("fail_details", ""),
                    error_log.get("test_item", ""),
                    error_log.get("fault_type1", ""),
                    error_log.get("fault_type2", ""),
                    error_log.get("fault_type3", ""),
                ],
            )
        )
        logger.debug(
            "知识库检索 _run_analysis",
            extra={"sn": sn, "search_query": search_query[:200]},
        )
        if search_query.strip():
            result = await ragflow_service.search_knowledge_base(
                question=search_query, top_k=RAG_TOP_K
            )
            refs = result.get("references", [])
            logger.debug("知识库检索结果", extra={"sn": sn, "refs_count": len(refs)})
            if refs:
                seen = {}
                for ref in refs:
                    seen.setdefault(ref.get("doc_name", "未知"), []).append(
                        ref.get("content", "")
                    )
                kb_lines = [
                    "## 知识库参考文档\n从知识库中检索到的相关技术文档（已按文档去重）："
                ]
                for idx, (doc_name, chunks) in enumerate(seen.items(), 1):
                    merged = "\n".join(chunks)
                    kb_lines.append(
                        f"\n[参考 {idx}] 来源: {doc_name}\n    内容: {merged}"
                    )
                    refs_result.append({"source": doc_name, "content": merged[:1000]})
                sections.append("\n".join(kb_lines))
            else:
                sections.append("（知识库未检索到匹配内容）")
        else:
            sections.append("（无可用检索条件）")
    except Exception as e:
        logger.warning(
            "知识库检索失败",
            extra={
                "sn": sn,
                "search_query": search_query[:200] if search_query else None,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        sections.append("（知识库检索异常）")

    # ── 上下文 Token 预算截断 ──
    max_tokens = llm_service.get_config_value("max_tokens", MAX_PROMPT_TOKENS)
    # 预留 4096 token 给 system prompt + 输出
    content_budget = max_tokens - 4096
    full_text = "\n\n".join(sections)
    estimated = _estimate_tokens(full_text)
    if estimated > max_tokens:
        logger.info(
            "上下文超出 token 上限: estimated=%d limit=%d content_budget=%d",
            estimated, max_tokens, content_budget,
        )
        truncated = []
        log_section_idx = next(
            (i for i, s in enumerate(sections) if s.startswith("## 日志文件尾部内容")),
            None,
        )
        kb_section_idx = next(
            (i for i, s in enumerate(sections) if s.startswith("## 知识库参考文档")),
            None,
        )
        for i, sec in enumerate(sections):
            if i == log_section_idx:
                # 日志部分截断到预算的 60%
                log_budget = int(content_budget * 0.6)
                log_sec = _truncate_to_budget(sec, log_budget, "日志内容")
                truncated.append(log_sec)
            elif i == kb_section_idx:
                # 知识库部分截断到预算的 30%
                kb_budget = int(content_budget * 0.3)
                kb_sec = _truncate_to_budget(sec, kb_budget, "知识库参考")
                truncated.append(kb_sec)
            else:
                truncated.append(sec)
        sections = truncated
        logger.info("上下文截断完成: sections=%d", len(sections))

    await send_progress("llm", "正在调用大模型深度诊断...")
    analysis = await llm_service.analyze_with_knowledge_stream(
        error_log, "\n\n".join(sections), send_token
    )

    now = utc_now_iso()
    cache_doc = {
        "error_log_id": error_log_id,
        "sn": error_log.get("sn", ""),
        "test_item": error_log.get("test_item", ""),
        **analysis,
        "knowledge_refs": list(
            {
                r["source"]: r
                for r in (analysis.get("knowledge_refs") or refs_result)
                if r.get("source")
            }.values()
        ),
        "log_content": log_tail,
        "created_at": now,
    }
    insert_result = await get_collection("diagnosis_cache").insert_one(cache_doc)

    return _build_cache_response(
        cache_doc,
        error_log_id,
        cache_doc["sn"],
        cache_doc["test_item"],
        now,
        str(insert_result.inserted_id),
    )


# ── 路由 ──


@router.post("/error-log/{error_log_id}/analyze")
async def analyze_error_log_with_kb(
    error_log_id: str,
    current_user: dict = Depends(get_current_user),
    log_base_url: str = Query(""),
    context: Optional[ErrorLogAnalyzeContext] = Body(None),
):
    logger.debug(
        "智能剖析请求 context=%s server_sn=%s factory_id=%s",
        context,
        context.server_sn if context else None,
        context.factory_id if context else None,
    )
    cache_col = get_collection("diagnosis_cache")
    cached = await cache_col.find_one({"error_log_id": error_log_id})
    if cached:

        async def _cached_stream():
            yield _sse(
                "done", {"success": True, "data": await _build_cached_response(cached)}
            )

        return StreamingResponse(_cached_stream(), media_type="text/event-stream")

    async def _runner(send_progress, send_token):
        return await _run_analysis(
            error_log_id,
            log_base_url,
            send_progress,
            send_token,
            context=context,
        )

    return StreamingResponse(
        _sse_wrap(_runner, "诊断分析失败"), media_type="text/event-stream"
    )


@router.post("/error-log/{error_log_id}/re-analyze")
async def re_analyze_error_log(
    error_log_id: str,
    current_user: dict = Depends(get_current_user),
    log_base_url: str = Query(""),
    context: Optional[ErrorLogAnalyzeContext] = Body(None),
):
    await get_collection("diagnosis_cache").delete_one({"error_log_id": error_log_id})
    return await analyze_error_log_with_kb(
        error_log_id, current_user, log_base_url, context
    )


# ── SSE 通用工具 ──


async def _sse_wrap(
    runner: Callable[
        [Callable[[str, str], Awaitable[None]], Callable[[str], Awaitable[None]]],
        Awaitable[dict],
    ],
    on_error_prefix: str = "诊断失败",
):
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
            logger.error("诊断超时（10分钟）", extra={"event": "diagnosis_timeout"})
            await queue.put(
                ("error", {"message": "诊断超时，大模型响应时间过长，请稍后重试"})
            )
        except Exception as e:
            msg = str(e) if isinstance(e, ValueError) else f"{on_error_prefix}: {e}"
            if isinstance(e, ValueError):
                logger.warning(msg)
            else:
                logger.exception(
                    "诊断异常", extra={"error": str(e), "error_type": type(e).__name__}
                )
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
async def diagnose_sn_stream(
    request: DiagnosisBySNRequest, current_user: dict = Depends(get_current_user)
):
    async def _runner(send_progress, send_token):
        (
            device,
            llm_logs,
            maintenance,
            all_logs,
            similar_cases,
            kb_context,
            failed_logs,
        ) = await _gather_sn_data(
            request.sn, request.factory, on_progress=send_progress
        )

        await send_progress("llm", "正在调用大模型深度诊断...")
        diagnosis = await llm_service.diagnose_sn(
            request.sn,
            device,
            llm_logs,
            maintenance,
            similar_cases,
            kb_context=kb_context,
            failed_logs=failed_logs,
        )

        return _build_sn_response(
            request.sn, diagnosis, maintenance, all_logs, similar_cases, failed_logs
        ).model_dump()

    return StreamingResponse(_sse_wrap(_runner), media_type="text/event-stream")


# ── SN 诊断历史记录 ──


@router.post("/sn/save-history", response_model=ApiResponse)
async def save_sn_history(
    request: SaveSnHistoryRequest, current_user: dict = Depends(get_current_user)
):
    """保存 SN 诊断结果到历史记录"""
    try:
        result = request.diagnosis_result
        doc = {
            "user_id": current_user["id"],
            "sn": request.sn,
            "factory": request.factory,
            "category": result.get("category", ""),
            "confidence": result.get("confidence", 0.0),
            "summary": result.get("summary", ""),
            "diagnosis_result": result,
            "chat_messages": [],
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
        col = get_collection("diagnosis_sn_history")
        insert_result = await col.insert_one(doc)
        logger.info(
            "诊断历史保存成功",
            extra={"sn": request.sn, "history_id": str(insert_result.inserted_id)},
        )
        return ApiResponse(success=True, data={"id": str(insert_result.inserted_id)})
    except Exception as e:
        logger.exception("保存诊断历史失败", extra={"sn": request.sn})
        return ApiResponse(success=False, error=f"保存失败: {e}")


@router.put("/sn/history/{history_id}/chat", response_model=ApiResponse)
async def append_chat_message(
    history_id: str,
    request: AppendChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """追加对话消息到历史记录"""
    try:
        col = get_collection("diagnosis_sn_history")
        result = await col.update_one(
            {"_id": parse_object_id(history_id), "user_id": current_user["id"]},
            {
                "$push": {
                    "chat_messages": {"role": request.role, "content": request.content}
                },
                "$set": {"updated_at": utc_now_iso()},
            },
        )
        if result.matched_count == 0:
            return ApiResponse(success=False, error="历史记录不存在或无权访问")
        logger.info(
            "追加对话成功", extra={"history_id": history_id, "role": request.role}
        )
        return ApiResponse(success=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("追加对话失败", extra={"history_id": history_id})
        return ApiResponse(success=False, error=f"追加失败: {e}")


@router.get("/sn/history", response_model=ApiResponse)
async def list_sn_history(
    sn: str = Query(""),
    factory: str = Query(""),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """查询 SN 诊断历史记录列表"""
    try:
        col = get_collection("diagnosis_sn_history")
        query: dict = {"user_id": current_user["id"]}
        if sn:
            query["sn"] = sn
        if factory:
            query["factory"] = factory

        total = await col.count_documents(query)
        docs = (
            await col.find(query, {"diagnosis_result": 0})
            .sort("created_at", -1)
            .skip((page - 1) * limit)
            .limit(limit)
            .to_list(limit)
        )

        items = [
            SnHistoryItem(
                id=str(d["_id"]),
                sn=d["sn"],
                factory=d.get("factory", ""),
                category=d.get("category", ""),
                confidence=d.get("confidence", 0.0),
                summary=d.get("summary", ""),
                created_at=d["created_at"],
            )
            for d in docs
        ]

        return ApiResponse(
            success=True,
            data={
                "items": [i.model_dump() for i in items],
                "total": total,
                "page": page,
                "limit": limit,
            },
        )
    except Exception as e:
        logger.exception(
            "查询诊断历史失败", extra={"sn": sn, "factory": factory, "page": page}
        )
        return ApiResponse(success=False, error=f"查询失败: {e}")


@router.get("/sn/history/{history_id}", response_model=ApiResponse)
async def get_sn_history_detail(
    history_id: str, current_user: dict = Depends(get_current_user)
):
    """查询单条诊断历史完整记录（含对话）"""
    try:
        col = get_collection("diagnosis_sn_history")
        doc = await col.find_one(
            {"_id": parse_object_id(history_id), "user_id": current_user["id"]}
        )
        if not doc:
            return ApiResponse(success=False, error="历史记录不存在或无权访问")

        return ApiResponse(
            success=True,
            data=SnHistoryDetail(
                id=str(doc["_id"]),
                sn=doc["sn"],
                factory=doc.get("factory", ""),
                diagnosis_result=doc.get("diagnosis_result", {}),
                chat_messages=doc.get("chat_messages", []),
                created_at=doc["created_at"],
                updated_at=doc.get("updated_at", doc["created_at"]),
                feedback_rating=doc.get("feedback_rating"),
                feedback_comment=doc.get("feedback_comment"),
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("查询诊断历史详情失败", extra={"history_id": history_id})
        return ApiResponse(success=False, error=f"查询失败: {e}")


# ── 诊断反馈 ──


@router.post("/feedback", response_model=ApiResponse)
async def submit_diagnosis_feedback(
    request: DiagnosisFeedbackRequest,
    current_user: dict = Depends(get_current_user),
):
    """提交诊断反馈 - 用于收集用户对 AI 诊断结果的评价"""
    try:
        # 验证：解决一部分/没有解决时必须提供反馈内容
        if request.rating in ("partially", "unsolved") and not request.comment:
            return ApiResponse(
                success=False,
                error="请提供具体的反馈内容，帮助我们改进模型和知识库",
            )

        # 构建反馈文档
        feedback_doc = {
            "user_id": current_user["id"],
            "history_id": request.history_id,
            "sn": request.sn,
            "factory": request.factory,
            "rating": request.rating,
            "comment": request.comment,
            "diagnosis_context": request.diagnosis_context,
            "created_at": utc_now_iso(),
        }

        # 写入 MongoDB
        col = get_collection("diagnosis_feedback")
        insert_result = await col.insert_one(feedback_doc)

        # 如果提供了 history_id，更新历史记录中的反馈字段
        if request.history_id:
            await get_collection("diagnosis_sn_history").update_one(
                {"_id": parse_object_id(request.history_id), "user_id": current_user["id"]},
                {
                    "$set": {
                        "feedback_rating": request.rating,
                        "feedback_comment": request.comment,
                        "feedback_at": utc_now_iso(),
                    }
                },
            )

        logger.info(
            "诊断反馈已提交",
            extra={
                "feedback_id": str(insert_result.inserted_id),
                "history_id": request.history_id,
                "sn": request.sn,
                "rating": request.rating,
            },
        )
        return ApiResponse(
            success=True,
            data={"id": str(insert_result.inserted_id)},
            message="感谢您的反馈！",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("提交诊断反馈失败", extra={"sn": request.sn, "rating": request.rating})
        return ApiResponse(success=False, error=f"提交失败: {e}")

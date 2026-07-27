import asyncio
import json
import logging
import re
from ..core.utils import (
    utc_now_iso,
    is_sims_record_failed,
    validate_log_path,
    parse_object_id,
    build_log_download_url,
)
from typing import Awaitable, Callable, Literal, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..core.auth import get_current_user, is_admin_user
from ..core.factory_config import get_factory_by_id, load_factories_from_yaml
from ..core.mongodb import get_collection
from ..models.request import (
    DiagnosisBySNRequest,
    DiagnosisFollowUpRequest,
    SaveSnHistoryRequest,
    AppendChatRequest,
    ErrorLogAnalyzeContext,
    DiagnosisFeedbackRequest,
    DiagnosisFeedbackStatusRequest,
    DiagnosisFeedbackKnowledgeRequest,
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
from ..services.log_processing.prompt_registry import PromptRegistry
from ..services.mes_direct_service import MESDirectService, MESRequestError
from ..services import ragflow_service

logger = logging.getLogger(__name__)

MAX_LOG_BYTES = 2 * 1024 * 1024
LOG_TAIL_CHARS = 3000  # 每个日志文件取末尾最多 3000 字符，避免单行长日志导致上下文过长
RAG_TOP_K = 10

# LLM 上下文窗口安全限制（为模型最大上下文留出 4096 token 余量给 system prompt 和输出）
# 例如模型 32K → MAX_PROMPT_TOKENS ≈ 28K
MAX_PROMPT_TOKENS = 28_000

router = APIRouter(prefix="/diagnosis", tags=["诊断"])

ProgressStatus = Literal["running", "skipped"]
ProgressMetadata = dict[str, object]
ProgressCallback = Callable[
    [str, str, ProgressStatus, Optional[ProgressMetadata]], Awaitable[None]
]


class _BoundedByteCollector:
    """以固定内存保留下载内容的头部和尾部，并统计完整源大小。"""

    def __init__(self, limit: int = MAX_LOG_BYTES):
        self.limit = max(2, limit)
        self.head_limit = self.limit // 2
        self.tail_limit = self.limit - self.head_limit
        self.head = bytearray()
        self.tail = bytearray()
        self.source_size = 0
        self.source_line_count = 0
        self.last_byte: Optional[int] = None

    def feed(self, chunk: bytes) -> None:
        if not chunk:
            return
        self.source_size += len(chunk)
        self.source_line_count += chunk.count(b"\n")
        self.last_byte = chunk[-1]
        head_remaining = self.head_limit - len(self.head)
        if head_remaining > 0:
            self.head.extend(chunk[:head_remaining])
            chunk = chunk[head_remaining:]
        if chunk:
            self.tail.extend(chunk)
            if len(self.tail) > self.tail_limit:
                del self.tail[: len(self.tail) - self.tail_limit]

    def result(self) -> tuple[bytes, dict]:
        truncated = self.source_size > self.limit
        if truncated:
            raw = bytes(self.head) + b"\n[... download middle omitted ...]\n" + bytes(self.tail)
        else:
            raw = bytes(self.head + self.tail)
        return raw, {
            "source_size": self.source_size,
            "downloaded_size": min(self.source_size, self.limit),
            "source_line_count": self.source_line_count
            + (1 if self.source_size and self.last_byte != ord("\n") else 0),
            "source_truncated": truncated,
            "truncation_strategy": "head_tail" if truncated else "none",
        }


def _unpack_full_download(result: tuple) -> tuple[str, dict, Optional[str]]:
    """兼容旧测试/调用方的 (content, error) 返回形态。"""
    if len(result) == 3:
        content, metadata, error = result
        return content, metadata, error
    content, error = result
    size = len(str(content).encode("utf-8", errors="replace"))
    return content, {
        "source_size": size,
        "downloaded_size": size,
        "source_line_count": len(str(content).splitlines()),
        "source_truncated": False,
        "truncation_strategy": "none",
    }, error


# ── 通用诊断 ──


def _machine_model_from_server(server: object) -> str:
    """从 MES 服务器信息中取实际机型，兼容 productModels 回退。"""
    model = str(getattr(server, "model", "") or "").strip()
    if model:
        return model
    product_models = str(getattr(server, "product_models", "") or "")
    return next((item.strip() for item in product_models.split(",") if item.strip()), "")


async def _gather_sn_data(
    sn: str,
    factory: str,
    on_progress: Optional[ProgressCallback] = None,
) -> tuple[dict, list[dict], list[dict], list[dict], list[dict], str, list[dict], list[dict], str]:
    """收集 SN 诊断所需数据。

    Returns:
        (device, llm_logs, maintenance, all_logs, similar_cases, kb_context,
         failed_logs, failed_log_files, merged_error_log)
    """
    async def _progress(
        s: str,
        d: str,
        status: ProgressStatus = "running",
        metadata: Optional[ProgressMetadata] = None,
    ) -> None:
        if on_progress:
            await on_progress(s, d, status, metadata)

    factory_cfg = get_factory_by_id(factory)
    if not factory_cfg:
        raise ValueError(f"厂区不存在: {factory}")
    factory_label = factory_cfg["name"]

    await _progress("device", "正在查询设备信息...")
    device = await knowledge_graph.get_device_by_sn(sn)
    machine_model = str((device or {}).get("model", "") or "").strip()

    sims_path = "/stepsmanagement/resultInfo/queryTestList.action"
    sims_params = {"start": 0, "limit": 50, "serverSN": sn, "customerID": ""}
    async with MESDirectService() as mes:
        if not machine_model:
            try:
                server = await mes.get_server(factory, sn)
                machine_model = _machine_model_from_server(server)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "MES 机型查询失败，使用默认提取 Prompt sn=%s factory=%s error=%s",
                    sn,
                    factory,
                    e,
                )

        if not device:
            device = {
                "id": "",
                "sn": sn,
                "model": machine_model,
                "factory": factory,
            }
        elif machine_model and not device.get("model"):
            device = {**device, "model": machine_model}

        await _progress(
            "prompt",
            f"正在加载机型 {machine_model or 'default'} 的日志提取 Prompt...",
        )
        extraction_prompt = await PromptRegistry().get_prompt(machine_model)
        logger.info(
            "日志提取 Prompt 已解析 sn=%s machine_model=%s prompt_model=%s",
            sn,
            machine_model or "default",
            extraction_prompt.get("model", "default"),
        )
        await _progress(
            "prompt",
            f"已加载机型 {machine_model or 'default'} 的日志提取 Prompt",
            "running",
            {
                "machine_model": machine_model or "default",
                "prompt_model": extraction_prompt.get("model", "default"),
                "system_prompt": extraction_prompt.get("system_prompt", ""),
                "user_template": extraction_prompt.get("user_template", ""),
            },
        )

        await _progress("sims", f"正在向 SIMS（{factory_label}）实时查询测试数据...")
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

    # 最终诊断只接收异常测试项；完整测试记录仍通过 all_logs 返回给前端展示。
    llm_logs = failed_logs

    failed_logs_with_path = [
        log for log in failed_logs if (log.get("log_path") or "").strip()
    ]
    if not failed_logs:
        skip_reason = "未发现失败测试项，无错误日志需要处理"
    elif not failed_logs_with_path:
        skip_reason = (
            f"发现 {len(failed_logs)} 条失败测试项，但均未提供日志路径"
        )
    else:
        skip_reason = ""

    if skip_reason:
        logger.info(
            "跳过 AI 错误日志提取 sn=%s failed_count=%d with_path_count=%d reason=%s",
            sn,
            len(failed_logs),
            len(failed_logs_with_path),
            skip_reason,
        )
        for stage, detail in (
            ("log_download", skip_reason),
            ("log_split", "没有可拆分的失败项原文日志"),
            ("log_extract", "没有可提交给 AI 提取的错误日志分段"),
            ("log_merge", "没有可聚合的错误日志提取结果"),
        ):
            metadata = {"file_count": 0} if stage == "log_download" else None
            await _progress(stage, detail, "skipped", metadata)

    _log_file_context, failed_log_files = await _download_failed_item_logs(
        log_base_url=factory_cfg.get("log_base_url", ""),
        failed_logs=failed_logs,
        factory_label=factory_label,
        ftp_user=factory_cfg.get("log_ftp_user"),
        ftp_password=factory_cfg.get("log_ftp_password"),
        on_progress=_progress if on_progress else None,
        sn=sn,
        factory=factory,
        machine_model=machine_model,
        extraction_prompt=extraction_prompt,
    )
    merged_error_log = _merge_extracted_log_files(sn, failed_log_files)

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

        query_parts = search_terms[:15]
        if merged_error_log:
            query_parts.append(merged_error_log[:12_000])
        query = "\n".join(query_parts)
        logger.debug("知识库检索 _gather_sn_data", extra={"sn": sn, "query": query[:200]})
        if query.strip():
            kb_result = await ragflow_service.search_knowledge_base(
                question=query, top_k=RAG_TOP_K
            )
            if kb_result.get("warning"):
                await _progress("ragflow", str(kb_result["warning"]), "skipped")
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

    if merged_error_log:
        merged_section = f"## 聚合错误日志（自适应提取）\n{merged_error_log}"
        kb_context = f"{kb_context}\n\n{merged_section}" if kb_context else merged_section

    return (
        device,
        llm_logs,
        maintenance,
        all_logs,
        similar_cases,
        kb_context,
        failed_logs,
        failed_log_files,
        merged_error_log,
    )


def _merge_extracted_log_files(sn: str, log_files: list[dict]) -> str:
    """Build the consolidated UTF-8 artifact used by RAG, diagnosis, and download."""
    if not log_files:
        return ""
    parts = [f"# SN {sn} 聚合错误日志", f"日志文件数: {len(log_files)}"]
    for index, log_file in enumerate(log_files, 1):
        parts.extend(
            [
                "",
                f"## [{index}] {log_file.get('test_item', '未知测试项')}",
                f"测试时间: {log_file.get('test_time', '')}",
                f"日志路径: {log_file.get('log_path', '')}",
                (
                    f"提取结果: {log_file.get('matched_lines', 0)} 个错误模式 / "
                    f"原日志 {log_file.get('total_lines', 0)} 行"
                ),
                "",
                str(log_file.get("extracted_content", "")),
            ]
        )
    return "\n".join(parts).strip() + "\n"


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
    failed_log_files: Optional[list[dict]] = None,
    merged_error_log: str = "",
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
        failed_log_files=failed_log_files or [],
        merged_error_log=merged_error_log,
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
            failed_log_files,
            merged_error_log,
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
                "failed_log_files": len(failed_log_files),
            },
        )
        return ApiResponse(
            success=True,
            data=_build_sn_response(
                request.sn,
                diagnosis,
                maintenance,
                all_logs,
                similar_cases,
                failed_logs,
                failed_log_files,
                merged_error_log,
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

        content, download_metadata, dl_error = _unpack_full_download(
            await _download_log_tail_fetch_full(
            log_base_url,
            safe_path,
            ftp_user=factory_info.get("log_ftp_user"),
            ftp_password=factory_info.get("log_ftp_password"),
            )
        )
        if dl_error:
            return ApiResponse(success=False, error=dl_error)
        if not content:
            return ApiResponse(success=False, error="日志内容为空")
        return ApiResponse(
            success=True,
            data={"content": content, "download_metadata": download_metadata},
        )
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
    configured_url = ((factory_info or {}).get("log_base_url") or "").strip()
    # A known factory is authoritative; do not let clients redirect server-side downloads.
    base_url = configured_url or (log_base_url_query or "").strip()
    if not factory_info:
        return base_url, None, None
    return (
        base_url,
        factory_info.get("log_ftp_user"),
        factory_info.get("log_ftp_password"),
    )


# ── 智能日志提取（替代原本的简单 tail 截断） ──


async def _resolve_machine_model(sn: str, factory: str) -> str:
    """解析 SN 对应的机型（用于选择按机型配置的提取 prompt）。

    优先查 devices 集合，回退 MES 实时查询；均失败返回 ""（使用默认 prompt）。
    """
    if not sn:
        return ""
    try:
        device = await knowledge_graph.get_device_by_sn(sn)
        if device and device.get("model"):
            return str(device["model"])
    except Exception as e:  # noqa: BLE001
        logger.debug("get_device_by_sn 解析机型失败 sn=%s: %s", sn, e)
    try:
        async with MESDirectService() as mes:
            server = await mes.get_server(factory, sn)
            machine_model = _machine_model_from_server(server)
            if machine_model:
                return machine_model
    except Exception as e:  # noqa: BLE001
        logger.debug("mes.get_server 解析机型失败 sn=%s: %s", sn, e)
    return ""


async def _download_and_extract_log(
    log_base_url: str,
    log_path: str,
    *,
    ftp_user: Optional[str] = None,
    ftp_password: Optional[str] = None,
    extraction_mode: str = "balanced",
    sn: str = "",
    factory: str = "",
    machine_model: str = "",
    extraction_prompt: Optional[dict] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> tuple[str, dict]:
    """
    下载日志文件并执行「智能日志提取」（独立日志处理模块）。

    流程：解析机型对应 prompt → 按提取模型上下文窗口分段 →
    并发调用快速提取模型抽取各段错误 → 聚合；AI 不可用 / 全部失败时回退编码级提取。

    返回:
        (extracted_text, stats_dict)
        stats_dict 含 ai_extracted / segment_count / model_used / error_count 等字段。
    """
    from ..services.log_processing import process_log

    safe_log_path = validate_log_path(log_path)
    if on_progress:
        await on_progress(
            "log_download",
            f"正在下载日志 {safe_log_path.rsplit('/', 1)[-1]}",
            "running",
            None,
        )

    # 流式下载；超出安全上限时仅保留头尾，并携带明确的截断元数据。
    content, download_metadata, dl_error = _unpack_full_download(
        await _download_log_tail_fetch_full(
            log_base_url,
            safe_log_path,
            ftp_user=ftp_user,
            ftp_password=ftp_password,
        )
    )
    if dl_error:
        return "", {"error": dl_error, "matched_lines": 0, "paragraphs": 0, "total_lines": 0}
    if not content.strip():
        return "", {"error": "日志内容为空", "matched_lines": 0, "paragraphs": 0, "total_lines": 0}

    # 解析机型（若调用方未显式传入）
    if not machine_model:
        machine_model = await _resolve_machine_model(sn, factory)

    async def processing_progress(stage: str, detail: str) -> None:
        if on_progress:
            await on_progress(stage, detail, "running", None)

    # 智能提取（AI 分段并发，失败/未配置自动回退编码级）
    result = await process_log(
        content,
        machine_model,
        prompt_config=extraction_prompt,
        mode=extraction_mode,
        on_progress=processing_progress if on_progress else None,
    )
    result["stats"].update(download_metadata)
    return result["extracted"], result["stats"]


async def _download_log_tail_fetch_full(
    log_base_url: str,
    log_path: str,
    *,
    ftp_user: Optional[str] = None,
    ftp_password: Optional[str] = None,
) -> tuple[str, dict, Optional[str]]:
    """
    获取日志内容（供智能提取使用），使用 MAX_LOG_BYTES 固定内存上限。
    超限时保留头尾各一半，避免只看文件末尾而漏掉启动阶段异常。
    """
    from ..core.utils import build_log_download_url

    if not log_base_url or not log_path:
        return "", {}, "log_base_url 或 log_path 为空"
    url = build_log_download_url(log_base_url, log_path)
    if not url:
        return "", {}, "log_base_url 或 log_path 为空"

    try:
        if url.startswith("ftp://"):
            return await _download_ftp_full(url, ftp_user=ftp_user, ftp_password=ftp_password)

        async with httpx.AsyncClient(timeout=30) as client:
            collector = _BoundedByteCollector()
            async with client.stream("GET", url) as resp:
                if resp.is_error:
                    await resp.aread()
                    resp.raise_for_status()
                async for chunk in resp.aiter_bytes(64 * 1024):
                    collector.feed(chunk)
            raw, metadata = collector.result()
            text = raw.decode(resp.encoding or "utf-8", errors="replace")

            # HTML 日志转纯文本
            if url.endswith(".html"):
                try:
                    from lxml import html as lxml_html
                    tree = lxml_html.fromstring(text)
                    for tag in ("script", "style"):
                        for elem in list(tree.iter(tag)):
                            elem.drop_tree()
                    lines = [ln for ln in tree.text_content().strip().splitlines() if ln.strip()]
                    return "\n".join(lines), metadata, None
                except Exception as e:
                    logger.warning(
                        "HTML 解析失败 url=%s error_type=%s error=%s",
                        url, type(e).__name__, e,
                    )

            if metadata["source_truncated"]:
                logger.info(
                    "日志超出 %d 字节上限，保留头尾 url=%s source_bytes=%d",
                    MAX_LOG_BYTES,
                    url,
                    metadata["source_size"],
                )
            return text, metadata, None

    except httpx.HTTPStatusError as e:
        detail = f"HTTP 日志下载失败: {e.response.status_code} {e.response.reason_phrase} url={url}"
        logger.warning("%s body_preview=%s", detail, (e.response.text or "")[:200])
        return "", {}, detail
    except httpx.RequestError as e:
        detail = f"HTTP 日志下载网络错误 url={url} error={type(e).__name__}: {e}"
        logger.warning(detail)
        return "", {}, detail
    except Exception as e:
        detail = f"日志下载失败 url={url} error={type(e).__name__}: {e}"
        logger.warning(detail)
        return "", {}, detail


async def _download_ftp_full(
    url: str,
    *,
    ftp_user: Optional[str] = None,
    ftp_password: Optional[str] = None,
) -> tuple[str, dict, Optional[str]]:
    """FTP 下载日志完整内容（供智能提取使用）。"""
    from urllib.parse import urlparse, unquote
    import ftplib

    if not _ftp_has_explicit_credentials(url, ftp_user, ftp_password):
        return await _download_ftp_full_urlopen(url)

    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 21
    path = unquote(parsed.path or "")
    auth_user = unquote(parsed.username) if parsed.username else (ftp_user or "anonymous")
    auth_password = (
        unquote(parsed.password) if parsed.password is not None
        else (ftp_password if ftp_password is not None else "")
    )

    try:
        loop = asyncio.get_event_loop()
        collector = _BoundedByteCollector()

        def _ftp_download():
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=30)
            ftp.login(auth_user, auth_password)
            ftp.retrbinary(f"RETR {path}", collector.feed, blocksize=64 * 1024)
            ftp.quit()

        await loop.run_in_executor(None, _ftp_download)
        raw, metadata = collector.result()
        text = raw.decode("utf-8", errors="replace")
        if metadata["source_truncated"]:
            logger.info(
                "FTP 日志超出 %d 字节上限，保留头尾 url=%s source_bytes=%d",
                MAX_LOG_BYTES,
                url,
                metadata["source_size"],
            )
        return text, metadata, None
    except Exception as e:
        detail = _describe_ftp_error(e, host=host, port=port, path=path,
                                      auth_user=auth_user,
                                      used_anonymous=(auth_user == "anonymous"))
        logger.warning(detail)
        return "", {}, detail


async def _download_ftp_full_urlopen(url: str) -> tuple[str, dict, Optional[str]]:
    """无显式凭据的 FTP 下载，使用固定内存的头尾采集器。"""
    import urllib.request

    def _fetch() -> tuple[bytes, dict]:
        collector = _BoundedByteCollector()
        with urllib.request.urlopen(url, timeout=30) as response:
            while chunk := response.read(64 * 1024):
                collector.feed(chunk)
        return collector.result()

    try:
        loop = asyncio.get_running_loop()
        raw, metadata = await loop.run_in_executor(None, _fetch)
        return raw.decode("utf-8", errors="replace"), metadata, None
    except Exception as e:
        detail = f"FTP 日志下载失败 url={url} error={type(e).__name__}: {e}"
        logger.warning(detail)
        return "", {}, detail


async def _download_failed_item_logs(
    *,
    log_base_url: str,
    failed_logs: list[dict],
    factory_label: str,
    ftp_user: Optional[str] = None,
    ftp_password: Optional[str] = None,
    on_progress: Optional[ProgressCallback] = None,
    max_files: int = 2,
    sn: str = "",
    factory: str = "",
    machine_model: str = "",
    extraction_prompt: Optional[dict] = None,
) -> tuple[str, list[dict]]:
    """下载失败项原文日志（使用智能提取替代简单 tail 截断）。

    Returns:
        (markdown_block, failed_log_files)
        - markdown_block: 拼入 kb_context 的 Markdown 字符串
        - failed_log_files: 每项含 {test_item, test_time, log_path,
          extracted_content, matched_lines, total_lines}
    """
    with_path = [fl for fl in failed_logs if (fl.get("log_path") or "").strip()]
    if not with_path:
        return "", []

    latest_logs = sorted(
        with_path,
        key=lambda log: _normalize_test_time(log.get("test_time", "")),
        reverse=True,
    )[:max_files]

    selected_logs: list[dict] = []
    seen_dedupe_keys: set[tuple[str, str]] = set()
    for failed_log in latest_logs:
        log_path = (failed_log.get("log_path") or "").strip()
        test_item = (failed_log.get("test_item") or "").strip()
        dedupe_key = ("test_item", test_item) if test_item else ("log_path", log_path)
        if dedupe_key in seen_dedupe_keys:
            continue
        seen_dedupe_keys.add(dedupe_key)
        selected_logs.append(failed_log)

    if not log_base_url:
        raise ValueError(
            f"厂区「{factory_label}」未配置 log_base_url，无法下载失败项原文日志，已中止诊断。"
        )

    if on_progress:
        await on_progress(
            "log_download",
            f"正在分析最新 {max_files} 条失败日志（按测试项目去重后 {len(selected_logs)} 个文件）...",
            "running",
            {"file_count": len(selected_logs)},
        )

    blocks: list[str] = []
    errors: list[str] = []
    non_anomalous_count = 0
    failed_log_files: list[dict] = []

    for fl in selected_logs:
        log_path = (fl.get("log_path") or "").strip()
        # 使用智能提取（AI 分段并发 + 编码级回退）替代原本的 tail 截断
        extracted, stats = await _download_and_extract_log(
            log_base_url,
            log_path,
            ftp_user=ftp_user,
            ftp_password=ftp_password,
            extraction_mode="balanced",
            sn=sn,
            factory=factory,
            machine_model=machine_model,
            extraction_prompt=extraction_prompt,
            on_progress=on_progress,
        )
        dl_error = stats.get("error")
        if dl_error:
            errors.append(f"{fl.get('test_item', log_path)}: {dl_error}")
            continue

        original_lines = int(
            stats.get("preprocessing_original_lines")
            or stats.get("total_lines", 0)
            or 0
        )
        kept_lines = int(stats.get("preprocessing_kept_lines", original_lines) or 0)
        removed_lines = int(stats.get("preprocessing_removed_lines", 0) or 0)
        removal_rate = removed_lines / original_lines if original_lines else 0.0
        preprocessing_applied = bool(stats.get("preprocessing_applied", False))
        source_truncated = bool(stats.get("source_truncated", False))
        source_line_count = int(stats.get("source_line_count", original_lines) or 0)
        if source_truncated:
            comparison_detail = (
                f"{fl.get('test_item') or log_path}: 源文件约 {source_line_count} 行 / "
                f"{int(stats.get('source_size', 0) or 0)} 字节，下载时按头尾保留 "
                f"{int(stats.get('downloaded_size', 0) or 0)} 字节；采样内容 "
                f"{original_lines} 行，清洗后 {kept_lines} 行"
            )
        elif preprocessing_applied:
            comparison_detail = (
                f"{fl.get('test_item') or log_path}: 原文件 {original_lines} 行，"
                f"清洗后 {kept_lines} 行，过滤 {removed_lines} 行"
                f"（{removal_rate:.1%}）"
            )
        else:
            comparison_detail = (
                f"{fl.get('test_item') or log_path}: 原文件 {original_lines} 行，"
                "未触发规则清洗，全文进入后续提取"
            )
        comparison_metadata = {
            "test_item": fl.get("test_item", ""),
            "log_path": log_path,
            "original_lines": original_lines,
            "kept_lines": kept_lines,
            "removed_lines": removed_lines,
            "removal_rate": round(removal_rate, 4),
            "preprocessing_applied": preprocessing_applied,
            "recognized_level_lines": int(
                stats.get("preprocessing_level_lines", 0) or 0
            ),
            "anomaly_entries": int(
                stats.get("preprocessing_anomaly_entries", 0) or 0
            ),
        }
        if source_truncated:
            comparison_metadata.update(
                {
                    "source_size": int(stats.get("source_size", 0) or 0),
                    "downloaded_size": int(stats.get("downloaded_size", 0) or 0),
                    "source_line_count": source_line_count,
                    "source_truncated": True,
                    "truncation_strategy": stats.get("truncation_strategy", "head_tail"),
                }
            )
        if on_progress:
            await on_progress(
                "log_merge",
                comparison_detail,
                "running",
                {
                    "log_comparison": comparison_metadata
                },
            )

        detected_error_count = stats.get("error_count")
        if detected_error_count is None:
            detected_error_count = stats.get("matched_lines", 0)
        if not isinstance(detected_error_count, (int, float)) or detected_error_count <= 0:
            non_anomalous_count += 1
            logger.info(
                "日志未检测到异常，不加入最终分析 sn=%s log_path=%s",
                sn,
                log_path,
            )
            continue
        if not extracted.strip():
            errors.append(f"{fl.get('test_item', log_path)}: 日志内容为空")
            continue

        # 收集每项日志文件信息（供前端下载）
        failed_log_files.append({
            "test_item": fl.get("test_item", ""),
            "test_time": str(fl.get("test_time", "")),
            "log_path": log_path,
            "extracted_content": extracted,
            "matched_lines": stats.get("matched_lines", stats.get("error_count", 0)),
            "total_lines": stats.get("total_lines", 0),
            "ai_extracted": stats.get("ai_extracted", False),
            "processing_mode": stats.get("processing_mode", ""),
            "segment_count": stats.get("segment_count", 0),
            "successful_segments": stats.get("successful_segments", 0),
            "failed_segments": stats.get("failed_segments", 0),
            "extraction_duration_ms": stats.get("extraction_duration_ms", 0),
            "model_used": stats.get("model_used", ""),
            "prompt_model": stats.get("prompt_model", ""),
            "preprocessing_applied": stats.get("preprocessing_applied", False),
            "preprocessing_original_lines": stats.get(
                "preprocessing_original_lines", stats.get("total_lines", 0)
            ),
            "preprocessing_kept_lines": stats.get("preprocessing_kept_lines", 0),
            "preprocessing_removed_lines": stats.get("preprocessing_removed_lines", 0),
            "preprocessing_retention_ratio": stats.get(
                "preprocessing_retention_ratio", 1.0
            ),
            "preprocessing_level_lines": stats.get("preprocessing_level_lines", 0),
            "preprocessing_anomaly_entries": stats.get(
                "preprocessing_anomaly_entries", 0
            ),
            "source_size": stats.get("source_size", 0),
            "downloaded_size": stats.get("downloaded_size", 0),
            "source_line_count": stats.get("source_line_count", 0),
            "source_truncated": stats.get("source_truncated", False),
            "truncation_strategy": stats.get("truncation_strategy", "none"),
            "retry_count": stats.get("retry_count", 0),
        })

        if stats.get("ai_extracted"):
            scan_label = (
                f"（AI 提取: {stats.get('error_count', 0)} 个错误点 / "
                f"{stats.get('segment_count', 0)} 段 / 机型: {stats.get('model_used', 'default')}）"
            )
        else:
            scan_label = (
                f"（编码扫描: {stats.get('matched_lines', 0)} 个错误行 / "
                f"{stats.get('paragraphs', 0)} 个段落 / 共 {stats.get('total_lines', 0)} 行）"
            )

        blocks.append(
            f"### [{fl.get('test_time', '')}] {fl.get('test_item', '')}\n"
            f"路径: {log_path}\n"
            f"{scan_label}\n"
            f"```\n{extracted}\n```"
        )

    if not blocks:
        if non_anomalous_count:
            if on_progress:
                await on_progress(
                    "log_merge",
                    f"已检查 {non_anomalous_count} 个文件，均未检测到异常，未加入最终分析",
                    "running",
                    None,
                )
            return "", []
        detail = "；".join(errors[:3])
        if len(errors) > 3:
            detail += f" … 共 {len(errors)} 条失败"
        raise ValueError(f"失败项原文日志全部下载失败，已中止 AI 诊断: {detail}")

    if on_progress:
        msg = f"已提取 {len(blocks)} 份失败项原文日志"
        if errors:
            msg += f"（{len(errors)} 条下载失败已跳过）"
        if non_anomalous_count:
            msg += f"（{non_anomalous_count} 个文件未发现异常，未加入分析）"
        await on_progress("log_merge", msg, "running", None)

    markdown = "\n\n## 失败项原文日志（SIMS log_path — 智能提取）\n" + "\n\n".join(blocks)
    return markdown, failed_log_files


async def _download_log_tail(
    log_base_url: str,
    log_path: str,
    tail_chars: int = LOG_TAIL_CHARS,
    *,
    ftp_user: Optional[str] = None,
    ftp_password: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """下载日志尾部（按字符数截断）。返回 (content, error_message)，成功时 error_message 为 None。"""
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
                tail_chars,
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
            # 按字符数截断，优先保证行完整
            if len(text) > tail_chars:
                text = text[-tail_chars:]
                # 去掉开头的半行
                first_newline = text.find("\n")
                if 0 <= first_newline < 100:
                    text = text[first_newline + 1 :]
            return text, None
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
        "FTP 日志下载失败",
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


def _tail_text(raw: bytes, tail_chars: int) -> str:
    text = raw.decode("utf-8", errors="replace")
    if len(text) > MAX_LOG_BYTES:
        text = text[-MAX_LOG_BYTES:]
    # 按字符数截断，优先保证行完整
    if len(text) > tail_chars:
        text = text[-tail_chars:]
        first_newline = text.find("\n")
        if 0 <= first_newline < 100:
            text = text[first_newline + 1 :]
    return text


async def _download_log_tail_ftp_urlopen(url: str, tail_chars: int) -> tuple[str, Optional[str]]:
    """无凭据 FTP：与 download_ftp.py 一致，使用 urllib 直接拉取完整 URL。"""
    import urllib.request

    def _fetch() -> bytes:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()

    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, _fetch)
        content = _tail_text(raw, tail_chars)
        logger.debug("FTP urllib 下载成功 url=%s bytes=%s", url, len(raw))
        return content, None
    except Exception as e:
        detail = f"FTP 日志下载失败 url={url} error={type(e).__name__}: {e}"
        logger.warning(detail)
        return "", detail


async def _download_log_tail_ftp(
    url: str,
    tail_chars: int,
    *,
    ftp_user: Optional[str] = None,
    ftp_password: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """通过 FTP 下载日志尾部。无厂区凭据时优先 urllib；有凭据时用 ftplib。"""
    from urllib.parse import urlparse, unquote
    import ftplib
    import io

    if not _ftp_has_explicit_credentials(url, ftp_user, ftp_password):
        return await _download_log_tail_ftp_urlopen(url, tail_chars)

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
        content = _tail_text(buf.getvalue(), tail_chars)
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
    try:
        # 检查缓存
        cache_col = get_collection("diagnosis_cache")
        cached = await cache_col.find_one({"error_log_id": error_log_id})
        if cached:
            return ApiResponse(
                success=True, data=await _build_cached_response(cached)
            )

        # 运行分析（非流式）
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
                return ApiResponse(success=False, error="未找到异常日志")

        sn = error_log.get("sn", "")
        log_path = (error_log.get("log_path") or "").strip()
        resolved_url, ftp_user, ftp_password = _resolve_log_download_config(
            log_base_url,
            error_log.get("factory_id", ""),
        )
        log_tail = ""
        log_stats: dict = {}
        sections: list[str] = []

        if log_path:
            if not resolved_url:
                return ApiResponse(
                    success=False,
                    error="该记录有日志路径但厂区 log_base_url 未配置，已中止 AI 诊断。",
                )
            # 使用智能提取（AI 分段并发 + 编码级回退）替代原本的 tail 截断
            extracted, stats = await _download_and_extract_log(
                resolved_url,
                log_path,
                ftp_user=ftp_user,
                ftp_password=ftp_password,
                extraction_mode="balanced",
                sn=sn,
                factory=error_log.get("factory_id", ""),
            )
            dl_error = stats.get("error")
            if dl_error:
                return ApiResponse(success=False, error=f"日志下载失败，已中止 AI 诊断: {dl_error}")
            if not extracted.strip():
                return ApiResponse(success=False, error="日志下载成功但内容为空，已中止 AI 诊断。")
            # 将提取结果存入 log_tail（兼容原有缓存结构）
            log_tail = extracted
            log_stats = stats
            if stats.get("ai_extracted"):
                stat_line = (
                    f"（AI 提取: {stats.get('error_count', 0)} 个错误点 / "
                    f"{stats.get('segment_count', 0)} 段 / 机型: {stats.get('model_used', 'default')}）"
                )
            else:
                stat_line = (
                    f"（编码扫描: {stats.get('matched_lines', 0)} 个错误行 / "
                    f"{stats.get('paragraphs', 0)} 个段落 / 共 {stats.get('total_lines', 0)} 行）"
                )
            sections.append(
                f"## 聚合错误日志（自适应提取）\n{stat_line}\n```\n{extracted}\n```"
            )

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
                        log_tail[:12_000],
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
                exc_info=True,
            )
            sections.append("（知识库检索异常）")

        # 上下文 Token 预算截断
        max_tokens = llm_service.get_config_value("max_tokens", MAX_PROMPT_TOKENS) or MAX_PROMPT_TOKENS
        context_len = llm_service.get_config_value("model_context_len", 1000000) or 1000000
        safe_max_output = min(max_tokens, int(context_len * 0.7), context_len - 4096)
        safe_max_output = max(safe_max_output, 1024)
        content_budget = safe_max_output - 4096
        full_text = "\n\n".join(sections)
        estimated = _estimate_tokens(full_text)
        if estimated > safe_max_output:
            logger.info(
                "上下文超出 token 上限: estimated=%d limit=%d content_budget=%d",
                estimated, safe_max_output, content_budget,
            )
            truncated = []
            log_section_idx = next(
                (i for i, s in enumerate(sections) if s.startswith("## 日志文件内容")),
                None,
            )
            kb_section_idx = next(
                (i for i, s in enumerate(sections) if s.startswith("## 知识库参考文档")),
                None,
            )
            for i, sec in enumerate(sections):
                if i == log_section_idx:
                    log_budget = int(content_budget * 0.6)
                    log_sec = _truncate_to_budget(sec, log_budget, "日志内容")
                    truncated.append(log_sec)
                elif i == kb_section_idx:
                    kb_budget = int(content_budget * 0.3)
                    kb_sec = _truncate_to_budget(sec, kb_budget, "知识库参考")
                    truncated.append(kb_sec)
                else:
                    truncated.append(sec)
            sections = truncated
            logger.info("上下文截断完成: sections=%d", len(sections))

        error_count = (
            log_stats.get("error_count", log_stats.get("matched_lines", 0))
            if log_path
            else 0
        )
        analysis = await llm_service.analyze_with_knowledge(
            error_log, "\n\n".join(sections), error_count=error_count
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
            "log_extraction_stats": log_stats if log_path else {},
            "created_at": now,
        }
        insert_result = await get_collection("diagnosis_cache").insert_one(cache_doc)

        result_data = _build_cache_response(
            cache_doc,
            error_log_id,
            cache_doc["sn"],
            cache_doc["test_item"],
            now,
            str(insert_result.inserted_id),
        )
        return ApiResponse(success=True, data=result_data)
    except ValueError as e:
        logger.warning(
            "智能剖析参数错误",
            extra={"error_log_id": error_log_id, "error": str(e)},
        )
        return ApiResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception(
            "智能剖析失败", extra={"error_log_id": error_log_id}
        )
        return ApiResponse(success=False, error=f"分析失败: {e}")


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


# ── SN 诊断 SSE ──


@router.post("/sn/analyze")
async def diagnose_sn_stream(
    request: DiagnosisBySNRequest, current_user: dict = Depends(get_current_user)
):
    async def event_stream():
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def progress(
            stage: str,
            detail: str,
            status: ProgressStatus = "running",
            metadata: Optional[ProgressMetadata] = None,
        ) -> None:
            await queue.put(
                {
                    "type": "progress",
                    "stage": stage,
                    "detail": detail,
                    "status": status,
                    "meta": metadata or {},
                }
            )

        async def run_diagnosis() -> None:
            try:
                (
                    device,
                    llm_logs,
                    maintenance,
                    all_logs,
                    similar_cases,
                    kb_context,
                    failed_logs,
                    failed_log_files,
                    merged_error_log,
                ) = await _gather_sn_data(
                    request.sn,
                    request.factory,
                    on_progress=progress,
                )

                await progress("llm", "正在结合聚合错误日志和知识库进行诊断")
                diagnosis = await llm_service.diagnose_sn(
                    request.sn,
                    device,
                    llm_logs,
                    maintenance,
                    similar_cases,
                    kb_context=kb_context,
                    failed_logs=failed_logs,
                )
                response = _build_sn_response(
                    request.sn,
                    diagnosis,
                    maintenance,
                    all_logs,
                    similar_cases,
                    failed_logs,
                    failed_log_files,
                    merged_error_log,
                )
                await queue.put({"type": "result", "data": response.model_dump()})
            except ValueError as exc:
                logger.warning(
                    "SN 诊断参数错误",
                    extra={
                        "sn": request.sn,
                        "factory": request.factory,
                        "error": str(exc),
                    },
                )
                await queue.put({"type": "error", "error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "SN 诊断失败",
                    extra={"sn": request.sn, "factory": request.factory},
                )
                await queue.put({"type": "error", "error": f"诊断失败: {exc}"})

        task = asyncio.create_task(run_diagnosis())
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                if event.get("type") in {"result", "error"}:
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
            "user_itcode": current_user.get("itcode") or "",
            "user_name": current_user.get("name") or "",
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
        query: dict = {}
        if not is_admin_user(current_user):
            query["user_id"] = current_user["id"]
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
                user_id=str(d.get("user_id") or ""),
                user_itcode=d.get("user_itcode", ""),
                user_name=d.get("user_name", ""),
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
        query = {"_id": parse_object_id(history_id)}
        if not is_admin_user(current_user):
            query["user_id"] = current_user["id"]
        doc = await col.find_one(query)
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
                user_id=str(doc.get("user_id") or ""),
                user_itcode=doc.get("user_itcode", ""),
                user_name=doc.get("user_name", ""),
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("查询诊断历史详情失败", extra={"history_id": history_id})
        return ApiResponse(success=False, error=f"查询失败: {e}")


# ── 诊断反馈 ──


def _feedback_query(
    *,
    user_id: str = "",
    factory: str = "",
    rating: str = "",
    status: str = "",
    keyword: str = "",
) -> dict:
    clauses: list[dict] = []
    if user_id:
        clauses.append({"user_id": user_id})
    if factory:
        clauses.append({"factory": factory})
    if rating:
        clauses.append({"rating": rating})
    if status:
        if status == "pending":
            clauses.append(
                {
                    "$or": [
                        {"status": "pending"},
                        {"status": None},
                        {"status": {"$exists": False}},
                    ]
                }
            )
        else:
            clauses.append({"status": status})
    normalized_keyword = keyword.strip()
    if normalized_keyword:
        pattern = re.escape(normalized_keyword)
        clauses.append(
            {
                "$or": [
                    {"sn": {"$regex": pattern, "$options": "i"}},
                    {"comment": {"$regex": pattern, "$options": "i"}},
                    {"diagnosis_context": {"$regex": pattern, "$options": "i"}},
                ]
            }
        )
    if not clauses:
        return {}
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _serialize_feedback(doc: dict, fallback_user: Optional[dict] = None) -> dict:
    submitter = doc.get("submitter") or {}
    submitter_id = str(submitter.get("id") or doc.get("user_id") or "")
    fallback_email = ""
    if fallback_user and submitter_id == str(fallback_user.get("id") or ""):
        fallback_email = str(fallback_user.get("email") or "")
    return {
        "id": str(doc["_id"]),
        "history_id": doc.get("history_id"),
        "sn": doc.get("sn", ""),
        "factory": doc.get("factory", ""),
        "rating": doc.get("rating", "unsolved"),
        "comment": doc.get("comment") or "",
        "diagnosis_context": doc.get("diagnosis_context") or "",
        "status": doc.get("status") or "pending",
        "resolution_note": doc.get("resolution_note") or "",
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "knowledge_document_ids": doc.get("knowledge_document_ids", []),
        "knowledge_title": doc.get("knowledge_title", ""),
        "knowledge_uploaded_at": doc.get("knowledge_uploaded_at", ""),
        "submitter": {
            "id": submitter_id,
            "email": str(submitter.get("email") or fallback_email),
        },
    }


@router.get("/feedback", response_model=ApiResponse)
async def list_diagnosis_feedback(
    factory: str = Query(""),
    rating: Literal["", "solved", "partially", "unsolved"] = Query(""),
    status: Literal["", "pending", "processing", "resolved", "ignored"] = Query(""),
    keyword: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """分页查询诊断反馈并返回当前厂区/关键词范围内的汇总。"""
    col = get_collection("diagnosis_feedback")
    base_query = _feedback_query(
        user_id=current_user["id"],
        factory=factory,
        keyword=keyword,
    )
    list_query = _feedback_query(
        user_id=current_user["id"],
        factory=factory,
        rating=rating,
        status=status,
        keyword=keyword,
    )

    def with_filter(extra: dict) -> dict:
        return {"$and": [base_query, extra]} if base_query else extra

    try:
        total, solved, partially, unsolved, pending, processing = await asyncio.gather(
            col.count_documents(base_query),
            col.count_documents(with_filter({"rating": "solved"})),
            col.count_documents(with_filter({"rating": "partially"})),
            col.count_documents(with_filter({"rating": "unsolved"})),
            col.count_documents(
                with_filter(
                    {
                        "$or": [
                            {"status": "pending"},
                            {"status": None},
                            {"status": {"$exists": False}},
                        ]
                    }
                )
            ),
            col.count_documents(with_filter({"status": "processing"})),
        )
        filtered_total = await col.count_documents(list_query)
        cursor = (
            col.find(list_query)
            .sort("created_at", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return ApiResponse(
            success=True,
            data={
                "items": [_serialize_feedback(doc, current_user) for doc in docs],
                "total": filtered_total,
                "page": page,
                "limit": limit,
                "summary": {
                    "total": total,
                    "solved": solved,
                    "partially": partially,
                    "unsolved": unsolved,
                    "pending": pending,
                    "processing": processing,
                    "solved_rate": round(solved / total, 4) if total else 0,
                },
            },
        )
    except Exception as e:
        logger.exception("查询诊断反馈失败")
        return ApiResponse(success=False, error=f"查询反馈失败: {e}")


@router.patch("/feedback/{feedback_id}", response_model=ApiResponse)
async def update_diagnosis_feedback(
    feedback_id: str,
    request: DiagnosisFeedbackStatusRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新反馈处理状态和处理备注。"""
    now = utc_now_iso()
    col = get_collection("diagnosis_feedback")
    try:
        feedback_object_id = parse_object_id(feedback_id)
        result = await col.update_one(
            {"_id": feedback_object_id, "user_id": current_user["id"]},
            {
                "$set": {
                    "status": request.status,
                    "resolution_note": (request.resolution_note or "").strip(),
                    "updated_at": now,
                    "updated_by": current_user["id"],
                }
            },
        )
        if not result.matched_count:
            return ApiResponse(success=False, error="反馈不存在")
        doc = await col.find_one(
            {"_id": feedback_object_id, "user_id": current_user["id"]}
        )
        if not doc:
            return ApiResponse(success=False, error="反馈不存在")
        return ApiResponse(
            success=True,
            data=_serialize_feedback(doc, current_user),
            message="反馈状态已更新",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新诊断反馈失败", extra={"feedback_id": feedback_id})
        return ApiResponse(success=False, error=f"更新反馈失败: {e}")


@router.post("/feedback/{feedback_id}/knowledge", response_model=ApiResponse)
async def link_feedback_knowledge(
    feedback_id: str,
    request: DiagnosisFeedbackKnowledgeRequest,
    current_user: dict = Depends(get_current_user),
):
    """记录由反馈快速补充到知识库的文档。"""
    col = get_collection("diagnosis_feedback")
    now = utc_now_iso()
    try:
        feedback_object_id = parse_object_id(feedback_id)
        query = {"_id": feedback_object_id, "user_id": current_user["id"]}
        result = await col.update_one(
            query,
            {
                "$addToSet": {
                    "knowledge_document_ids": {"$each": request.document_ids}
                },
                "$set": {
                    "knowledge_title": request.knowledge_title,
                    "knowledge_uploaded_at": now,
                    "updated_at": now,
                    "updated_by": current_user["id"],
                },
            },
        )
        if not result.matched_count:
            return ApiResponse(success=False, error="反馈不存在")
        doc = await col.find_one(query)
        if not doc:
            return ApiResponse(success=False, error="反馈不存在")
        return ApiResponse(
            success=True,
            data=_serialize_feedback(doc, current_user),
            message="知识已补充并关联到反馈",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "关联反馈知识文档失败", extra={"feedback_id": feedback_id}
        )
        return ApiResponse(success=False, error=f"关联知识文档失败: {e}")


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
            "submitter": {
                "id": current_user["id"],
                "email": current_user.get("email") or "",
            },
            "history_id": request.history_id,
            "sn": request.sn,
            "factory": request.factory,
            "rating": request.rating,
            "comment": request.comment,
            "diagnosis_context": request.diagnosis_context,
            "status": "pending",
            "resolution_note": "",
            "knowledge_document_ids": [],
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

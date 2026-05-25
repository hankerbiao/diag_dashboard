from fastapi import APIRouter, Depends, HTTPException
from ..models.request import DiagnosisBySNRequest, DiagnosisByErrorLogRequest
from ..models.response import DiagnosisResponse, ErrorAnalysisResponse, ApiResponse
from ..services.llm_service import llm_service
from ..services.knowledge_graph import knowledge_graph
from ..core.auth import get_current_user

router = APIRouter(prefix="/diagnosis", tags=["诊断"])


@router.post("/sn", response_model=ApiResponse)
async def diagnose_by_sn(
    request: DiagnosisBySNRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    单机 SN 深度诊断

    1. 查询设备信息
    2. 查询测试日志
    3. 查询维修记录
    4. 检索相似案例
    5. 调用 LLM 生成诊断结果
    """
    try:
        # 1. 获取设备信息
        device = await knowledge_graph.get_device_by_sn(request.sn)
        if not device:
            return ApiResponse(
                success=False,
                error="未找到设备信息"
            )

        # 2. 获取测试日志
        test_logs = await knowledge_graph.get_device_test_logs(device["id"])

        # 3. 获取维修历史
        maintenance = await knowledge_graph.get_device_maintenance_history(device["id"])

        # 4. 检索相似案例
        similar_cases = await knowledge_graph.find_similar_cases(
            error_description=",".join([log.get("fail_details", "") for log in test_logs[:5]])
        )

        # 5. 调用 LLM 诊断
        diagnosis = await llm_service.diagnose_sn(
            sn=request.sn,
            device_info=device,
            test_logs=test_logs,
            maintenance=maintenance,
            similar_cases=similar_cases
        )

        return ApiResponse(
            success=True,
            data=DiagnosisResponse(
                sn=request.sn,
                category=diagnosis.get("category", "未知"),
                summary=diagnosis.get("summary", ""),
                confidence=diagnosis.get("confidence", 0.5),
                suggestions=diagnosis.get("suggestions", []),
                reference_logs=[],
                maintenance_history=[
                    {"id": m.get("id", ""), "date": m.get("date", ""),
                     "component": m.get("component", ""), "action": m.get("action", "")}
                    for m in maintenance[:5]
                ]
            )
        )

    except Exception as e:
        return ApiResponse(
            success=False,
            error=f"诊断失败: {str(e)}"
        )


@router.post("/error-log/{error_log_id}", response_model=ApiResponse)
async def analyze_error_log(
    error_log_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    异常日志 AI 分析

    1. 获取异常详情
    2. 检索相似案例
    3. 调用 LLM 分析
    """
    try:
        # 1. 获取异常日志 (mock)
        error_log = {
            "id": error_log_id,
            "sn": "6102263004319419",
            "test_item": "Stress Check",
            "test_time": "2026-05-14 21:27:48",
            "fail_details": "Stress Check failed, error code 0x822"
        }

        # 2. 检索相似案例
        similar_cases = await knowledge_graph.find_similar_cases(
            error_description=error_log["fail_details"]
        )

        # 3. 调用 LLM 分析
        analysis = await llm_service.analyze_error(
            error_log=error_log,
            similar_cases=similar_cases
        )

        return ApiResponse(
            success=True,
            data=ErrorAnalysisResponse(
                error_log=error_log,
                analysis=analysis.get("analysis", ""),
                root_cause=analysis.get("root_cause", ""),
                repair_suggestions=analysis.get("repair_suggestions", []),
                similar_cases=similar_cases
            )
        )

    except Exception as e:
        return ApiResponse(
            success=False,
            error=f"分析失败: {str(e)}"
        )
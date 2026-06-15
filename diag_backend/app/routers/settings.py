"""
全局 AI 配置 API
"""
from ..core.utils import utc_now_iso

from fastapi import APIRouter, Depends, HTTPException

from ..models.request import GlobalAiConfigUpdateRequest
from ..models.api import ApiResponse
from ..core.auth import get_current_user
from ..core.mongodb import get_collection

router = APIRouter(prefix="/settings", tags=["设置"])


def _mask_api_key(key: str) -> str:
    if len(key) <= 6:
        return "****"
    return key[:3] + "****" + key[-3:]


@router.get("/ai-config", response_model=ApiResponse)
async def get_global_ai_config(current_user: dict = Depends(get_current_user)):
    """获取全局 AI 配置（API Key 脱敏返回）"""
    try:
        col = get_collection("global_app_config")
        config = await col.find_one({"_id": "ai_config"})

        if config:
            return ApiResponse(
                success=True,
                data={
                    "api_key": _mask_api_key(config.get("api_key", "")),
                    "base_url": config.get("base_url", ""),
                    "model": config.get("model", ""),
                    "temperature": config.get("temperature", 0.7),
                    "max_tokens": config.get("max_tokens", 28000),
                    "provider": config.get("provider", "openai"),
                    "updated_at": config.get("updated_at", ""),
                    "updated_by": config.get("updated_by", ""),
                }
            )

        # 数据库无配置时返回空配置
        return ApiResponse(
            success=True,
            data={
                "api_key": "",
                "base_url": "",
                "model": "",
                "temperature": 0.7,
                "max_tokens": 28000,
                "provider": "openai",
                "updated_at": "",
                "updated_by": "",
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/ai-config", response_model=ApiResponse)
async def update_global_ai_config(
    request: GlobalAiConfigUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """更新全局 AI 配置并热加载到 LLM 服务（仅 admin）"""
    try:
        col = get_collection("global_app_config")

        update_data = {}
        if request.api_key is not None:
            # 跳过脱敏后的假值（前端回传了 GET 返回的 sk-****xyz）
            if "****" not in request.api_key:
                update_data["api_key"] = request.api_key
        if request.base_url is not None:
            update_data["base_url"] = request.base_url
        if request.model is not None:
            update_data["model"] = request.model
        if request.temperature is not None:
            update_data["temperature"] = request.temperature
        if request.provider is not None:
            update_data["provider"] = request.provider
        if request.max_tokens is not None:
            update_data["max_tokens"] = request.max_tokens

        update_data["updated_by"] = current_user["id"]
        update_data["updated_at"] = utc_now_iso()

        await col.update_one(
            {"_id": "ai_config"},
            {"$set": update_data},
            upsert=True
        )

        # 热加载 LLM 服务
        from ..services.llm_service import llm_service
        await llm_service.reload_config()

        return ApiResponse(
            success=True,
            message="AI 配置已更新，LLM 服务已热加载"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

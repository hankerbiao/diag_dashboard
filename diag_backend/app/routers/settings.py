"""
全局 AI 配置 API
"""
from ..core.utils import utc_now_iso

from fastapi import APIRouter, Depends, HTTPException

from ..models.request import GlobalAiConfigUpdateRequest, LogExtractionPromptRequest
from ..models.api import ApiResponse
from ..core.auth import get_current_user
from ..core.mongodb import get_collection
from ..services.log_processing import PromptRegistry

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
                    "temperature": config.get("temperature"),
                    "max_tokens": config.get("max_tokens"),
                    "chat_template_kwargs": config.get("chat_template_kwargs"),
                    "timeout": config.get("timeout"),
                    "provider": config.get("provider", ""),
                    "updated_at": config.get("updated_at", ""),
                    "updated_by": config.get("updated_by", ""),
                    # 错误日志提取模型（快速）—— 留空表示复用上方回答模型配置
                    "extraction_api_key": _mask_api_key(config.get("extraction_api_key", "")),
                    "extraction_base_url": config.get("extraction_base_url", ""),
                    "extraction_model": config.get("extraction_model", ""),
                    "extraction_max_tokens": config.get("extraction_max_tokens"),
                    "extraction_timeout": config.get("extraction_timeout"),
                }
            )

        # 数据库无配置时返回空配置
        return ApiResponse(
            success=True,
            data={
                "api_key": "",
                "base_url": "",
                "model": "",
                "temperature": None,
                "max_tokens": None,
                "chat_template_kwargs": None,
                "timeout": None,
                "provider": "",
                "updated_at": "",
                "updated_by": "",
                "extraction_api_key": "",
                "extraction_base_url": "",
                "extraction_model": "",
                "extraction_max_tokens": None,
                "extraction_timeout": None,
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
        if request.chat_template_kwargs is not None:
            update_data["chat_template_kwargs"] = request.chat_template_kwargs
        if request.timeout is not None:
            update_data["timeout"] = request.timeout
        # 错误日志提取模型（快速）配置
        if request.extraction_api_key is not None:
            if "****" not in (request.extraction_api_key or ""):
                update_data["extraction_api_key"] = request.extraction_api_key
        if request.extraction_base_url is not None:
            update_data["extraction_base_url"] = request.extraction_base_url
        if request.extraction_model is not None:
            update_data["extraction_model"] = request.extraction_model
        if request.extraction_max_tokens is not None:
            update_data["extraction_max_tokens"] = request.extraction_max_tokens
        if request.extraction_timeout is not None:
            update_data["extraction_timeout"] = request.extraction_timeout

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


@router.get("/machine-models", response_model=ApiResponse)
async def get_machine_models(current_user: dict = Depends(get_current_user)):
    """返回已存在的机型列表（用于按机型配置提取 prompt）。

    优先从 devices 聚合去重 model；为空时回退 sync_remote_servers.product_models。
    """
    try:
        models: list[str] = []
        devices_col = get_collection("devices")
        raw_models = await devices_col.distinct("model")
        models = [m for m in raw_models if m and isinstance(m, str)]

        if not models:
            servers_col = get_collection("sync_remote_servers")
            raw_pm = await servers_col.distinct("product_models")
            for r in raw_pm:
                if not r:
                    continue
                for part in str(r).split(","):
                    part = part.strip()
                    if part:
                        models.append(part)

        # 去重保序
        seen: set[str] = set()
        unique: list[str] = []
        for m in models:
            if m not in seen:
                seen.add(m)
                unique.append(m)
        return ApiResponse(success=True, data={"models": unique})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/log-extraction/prompts", response_model=ApiResponse)
async def list_log_extraction_prompts(current_user: dict = Depends(get_current_user)):
    """列出全部已配置的提取 prompt（含 default）。"""
    try:
        registry = PromptRegistry()
        prompts = await registry.list_prompts()
        return ApiResponse(success=True, data={"prompts": prompts})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/log-extraction/prompts", response_model=ApiResponse)
async def upsert_log_extraction_prompt(
    request: LogExtractionPromptRequest,
    current_user: dict = Depends(get_current_user),
):
    """新增或更新某机型的提取 prompt（model="default" 表示默认）。"""
    try:
        registry = PromptRegistry()
        await registry.upsert(
            request.model,
            request.system_prompt,
            request.user_template,
            updated_by=current_user.get("email", "system"),
        )
        return ApiResponse(success=True, message="提取 prompt 已保存")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/log-extraction/prompts/{model}", response_model=ApiResponse)
async def delete_log_extraction_prompt(
    model: str,
    current_user: dict = Depends(get_current_user),
):
    """删除某机型的提取 prompt；default 不可删。"""
    try:
        registry = PromptRegistry()
        await registry.delete(model)
        return ApiResponse(success=True, message="提取 prompt 已删除")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

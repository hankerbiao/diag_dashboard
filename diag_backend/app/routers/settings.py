"""
全局 AI 配置 API
"""

import asyncio

from ..core.utils import utc_now_iso

from fastapi import APIRouter, Depends, HTTPException

from ..models.request import (
    AiModelConnectivityTestRequest,
    GlobalAiConfigUpdateRequest,
    LogExtractionPromptRequest,
    RuntimeConfigUpdateRequest,
)
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
                    "extraction_api_key": _mask_api_key(
                        config.get("extraction_api_key", "")
                    ),
                    "extraction_base_url": config.get("extraction_base_url", ""),
                    "extraction_model": config.get("extraction_model", ""),
                    "extraction_max_tokens": config.get("extraction_max_tokens"),
                    "extraction_timeout": config.get("extraction_timeout"),
                },
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
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/ai-config", response_model=ApiResponse)
async def update_global_ai_config(
    request: GlobalAiConfigUpdateRequest, current_user: dict = Depends(get_current_user)
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

        await col.update_one({"_id": "ai_config"}, {"$set": update_data}, upsert=True)

        # 热加载 LLM 服务
        from ..services.llm_service import llm_service

        await llm_service.reload_config()

        return ApiResponse(success=True, message="AI 配置已更新，LLM 服务已热加载")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runtime-config", response_model=ApiResponse)
async def get_runtime_config(current_user: dict = Depends(get_current_user)):
    """获取运行时性能配置（日志提取并发）及默认值。"""
    try:
        from ..services.runtime_config_service import DEFAULTS, DOC_ID, runtime_config_service

        config = await runtime_config_service.get()
        meta = {"updated_at": "", "updated_by": ""}
        try:
            col = get_collection("global_app_config")
            doc = await col.find_one({"_id": DOC_ID})
            if doc:
                meta["updated_at"] = doc.get("updated_at", "")
                meta["updated_by"] = doc.get("updated_by", "")
        except Exception:  # noqa: BLE001
            pass
        return ApiResponse(
            success=True,
            data={
                "config": config,
                "defaults": dict(DEFAULTS),
                "generation": runtime_config_service.generation,
                **meta,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/runtime-config", response_model=ApiResponse)
async def update_runtime_config(
    request: RuntimeConfigUpdateRequest, current_user: dict = Depends(get_current_user)
):
    """更新运行时性能配置（日志提取并发）并实时生效。"""
    try:
        from ..services.runtime_config_service import runtime_config_service

        values = {}
        if request.per_request_concurrency is not None:
            values["per_request_concurrency"] = request.per_request_concurrency
        if request.global_concurrency is not None:
            values["global_concurrency"] = request.global_concurrency

        if not values:
            return ApiResponse(
                success=True,
                data={"config": await runtime_config_service.get()},
                message="无变更",
            )

        config = await runtime_config_service.apply_update(values)
        return ApiResponse(
            success=True,
            data={"config": config},
            message="并发配置已更新，对新的诊断请求实时生效",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _test_form_value(value, stored_value):
    return stored_value if value is None else value


def _test_secret_value(value: str | None, stored_value: str) -> str:
    if value is None or "****" in value:
        return stored_value
    return value


@router.post("/ai-config/test", response_model=ApiResponse)
async def test_ai_model_connectivity(
    request: AiModelConnectivityTestRequest,
    current_user: dict = Depends(get_current_user),
):
    """使用当前表单参数测试回答/提取模型，不保存配置。"""
    col = get_collection("global_app_config")
    stored = await col.find_one({"_id": "ai_config"}) or {}

    answer = {
        "api_key": _test_secret_value(request.api_key, stored.get("api_key", "")),
        "base_url": _test_form_value(request.base_url, stored.get("base_url", "")),
        "model": _test_form_value(request.model, stored.get("model", "")),
        "timeout": _test_form_value(request.timeout, stored.get("timeout", 30)),
    }
    extraction = {
        "api_key": _test_secret_value(
            request.extraction_api_key,
            stored.get("extraction_api_key", ""),
        ) or answer["api_key"],
        "base_url": _test_form_value(
            request.extraction_base_url,
            stored.get("extraction_base_url", ""),
        ) or answer["base_url"],
        "model": _test_form_value(
            request.extraction_model,
            stored.get("extraction_model", ""),
        ) or answer["model"],
        "timeout": _test_form_value(
            request.extraction_timeout,
            stored.get("extraction_timeout", 30),
        ) or answer["timeout"],
    }

    from ..services.llm_service import llm_service

    reused_answer = all(
        extraction.get(field) == answer.get(field)
        for field in ("api_key", "base_url", "model")
    )
    if reused_answer:
        answer_result = await llm_service.test_connection(answer)
        extraction_result = {**answer_result, "reused_answer": True}
    else:
        answer_result, extraction_result = await asyncio.gather(
            llm_service.test_connection(answer),
            llm_service.test_connection(extraction),
        )

    results = [
        {**answer_result, "service": "answer", "label": "诊断回答模型"},
        {**extraction_result, "service": "extraction", "label": "日志提取模型"},
    ]
    return ApiResponse(
        success=True,
        data={
            "all_connected": all(result.get("success") for result in results),
            "results": results,
        },
    )


@router.get("/machine-models", response_model=ApiResponse)
async def get_machine_models(current_user: dict = Depends(get_current_user)):
    """返回已存在的机型列表（用于按机型配置提取 prompt）。

    优先从 devices 聚合 model；为空时回退 sync_remote_servers.product_models，
    最后合并已手工配置 prompt 的机型。
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

        prompt_col = get_collection("log_extraction_prompts")
        configured_models = await prompt_col.distinct("_id")
        models.extend(
            model.strip()
            for model in configured_models
            if isinstance(model, str) and model.strip() and model != "default"
        )

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

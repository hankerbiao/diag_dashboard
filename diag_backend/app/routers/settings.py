"""
用户设置 API
"""
from fastapi import APIRouter, Depends, HTTPException

from ..models.request import SettingsUpdateRequest
from ..models.response import SettingsResponse, ApiResponse
from ..core.auth import get_current_user
from ..core.mongodb import get_collection

router = APIRouter(prefix="/settings", tags=["设置"])


@router.get("", response_model=ApiResponse)
async def get_settings(current_user: dict = Depends(get_current_user)):
    """获取用户设置"""
    try:
        col = get_collection("app_settings")
        settings_doc = await col.find_one({"user_id": current_user["id"]})

        if settings_doc:
            return ApiResponse(
                success=True,
                data=SettingsResponse(
                    ai_api_url=settings_doc.get("ai_api_url", "https://api.openai.com/v1"),
                    ai_model=settings_doc.get("ai_model", "gpt-4-turbo"),
                    ai_temperature=settings_doc.get("ai_temperature", 0.7),
                    active_kbs=settings_doc.get("active_kbs", ["MES", "SIMS", "Case Library"])
                )
            )

        # 默认设置
        return ApiResponse(
            success=True,
            data=SettingsResponse(
                ai_api_url="https://api.openai.com/v1",
                ai_model="gpt-4-turbo",
                ai_temperature=0.7,
                active_kbs=["MES", "SIMS", "Case Library"]
            )
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("", response_model=ApiResponse)
async def update_settings(
    request: SettingsUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """更新用户设置"""
    try:
        col = get_collection("app_settings")

        # 构建更新数据
        update_data = {
            "updated_at": "now()"
        }

        if request.ai_api_url is not None:
            update_data["ai_api_url"] = request.ai_api_url
        if request.ai_api_key is not None:
            update_data["ai_api_key"] = request.ai_api_key
        if request.ai_model is not None:
            update_data["ai_model"] = request.ai_model
        if request.ai_temperature is not None:
            update_data["ai_temperature"] = request.ai_temperature
        if request.active_kbs is not None:
            update_data["active_kbs"] = request.active_kbs

        # 检查是否存在
        existing = await col.find_one({"user_id": current_user["id"]})

        if existing:
            # 更新
            await col.update_one(
                {"user_id": current_user["id"]},
                {"$set": update_data}
            )
        else:
            # 创建
            update_data["user_id"] = current_user["id"]
            await col.insert_one(update_data)

        return ApiResponse(
            success=True,
            message="设置已保存"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
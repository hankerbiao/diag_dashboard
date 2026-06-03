"""
MES / SIMS 实时查询路由（只读）

历史测试数据写入 MongoDB 由仓库根目录 `scripts/weaveeye_sync.py` 独立执行，
不在 API 进程内触发同步或调度。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.auth import get_current_user
from ..models.api import ApiResponse
from ..services.mes_direct_service import MESDirectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["MES 实时查询"])


@router.get("/servers")
async def get_servers(
    factory_id: Optional[str] = Query(None, description="厂区标识，不传则查全部"),
    search_sn: Optional[str] = Query(None, description="服务器 SN 模糊搜索"),
    search_product_models: Optional[str] = Query(None, description="产品型号模糊搜索"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user),
):
    """查询服务器列表（实时从 MES API 获取）"""
    if not factory_id:
        return ApiResponse(
            success=True,
            data={"items": [], "total": 0, "page": page, "limit": limit},
            message="请选择厂区后查询",
        )

    try:
        async with MESDirectService() as mes:
            result = await mes.search_servers(
                factory_id=factory_id,
                sn=search_sn or "",
                product_models=search_product_models or "",
                page=page,
                limit=limit,
            )
        return ApiResponse(success=True, data=result)
    except ValueError as e:
        return ApiResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception("MES 服务器查询失败")
        return ApiResponse(success=False, error=f"MES API 查询失败: {e}")


@router.get("/servers/{server_sn}/test-details")
async def get_test_details(
    server_sn: str,
    factory_id: Optional[str] = Query(None, description="厂区标识"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=500, description="每页数量"),
    current_user: dict = Depends(get_current_user),
):
    """查询某服务器的测试详情（实时从 MES API 获取，支持分页）"""
    if not factory_id:
        return ApiResponse(success=False, error="必须指定 factory_id 参数")

    try:
        offset = (page - 1) * limit
        async with MESDirectService() as mes:
            result = await mes.get_test_details(
                factory_id, server_sn, offset=offset, limit=limit,
            )
        return ApiResponse(success=True, data={
            "items": result["items"],
            "total": result["total"],
            "page": page,
            "limit": limit,
        })
    except ValueError as e:
        return ApiResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception("MES 测试详情查询失败")
        return ApiResponse(success=False, error=f"MES API 查询失败: {e}")

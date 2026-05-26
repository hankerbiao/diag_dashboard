"""
厂区配置查询 - 从 YAML 配置文件中读取厂区列表（只读）
厂区数据由配置文件 configs/factories.yaml 管理
"""
import logging
from fastapi import APIRouter, Depends

from ..core.auth import get_current_user
from ..core.factory_config import load_factories_from_yaml
from ..models.response import ApiResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/factories", tags=["厂区管理"])


@router.get("")
async def list_factories(current_user: dict = Depends(get_current_user)):
    """获取所有厂区配置（从 YAML 配置文件读取）"""
    factories = load_factories_from_yaml()
    return ApiResponse(success=True, data=factories)

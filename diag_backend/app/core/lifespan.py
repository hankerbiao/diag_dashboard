"""应用生命周期管理"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """应用启动/关闭生命周期"""
    logger.info("=" * 60, extra={"event": "app_startup"})
    logger.info("WeaveEye API 服务启动中...", extra={"event": "app_startup"})

    # startup: 连接 MongoDB
    logger.info("正在连接 MongoDB...")
    from .mongodb import connect_mongodb, close_mongodb
    await connect_mongodb()
    from .config import get_settings

    app_settings = get_settings()
    logger.info("MongoDB 连接成功", extra={"event": "mongodb_connected", "uri": app_settings.mongodb_uri})

    # startup: 启动分析看板快照调度器
    logger.info("启动分析看板调度器...")
    from ..services.analytics_service import get_analytics_service
    analytics_service = get_analytics_service()
    analytics_service.start()
    logger.info("分析看板调度器已启动", extra={"event": "analytics_scheduler_started"})

    logger.info("=" * 60, extra={"event": "app_ready"})
    logger.info("WeaveEye API 服务启动完成 ✓")

    yield

    # shutdown
    logger.info("正在关闭服务...")
    logger.info("停止分析看板调度器...")
    await analytics_service.stop()
    logger.info("关闭 MongoDB 连接...")
    await close_mongodb()
    logger.info("服务已关闭 ✓", extra={"event": "app_shutdown"})

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

    from .config import get_settings, validate_auth_settings

    app_settings = get_settings()
    validate_auth_settings(app_settings)

    # startup: 连接 MongoDB
    logger.info("正在连接 MongoDB...")
    from .mongodb import connect_mongodb, close_mongodb
    await connect_mongodb()
    logger.info("MongoDB 连接成功", extra={"event": "mongodb_connected", "uri": app_settings.mongodb_uri})

    logger.info("=" * 60, extra={"event": "app_ready"})
    logger.info("WeaveEye API 服务启动完成 ✓")

    yield

    # shutdown
    logger.info("正在关闭服务...")
    logger.info("关闭 MongoDB 连接...")
    await close_mongodb()
    logger.info("服务已关闭 ✓", extra={"event": "app_shutdown"})

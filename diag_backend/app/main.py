from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from .routers import (
    analytics,
    diagnosis,
    error_logs,
    factories,
    knowledge_base,
    settings as settings_router,
    sync,
    auth,
)
from .core.config import get_settings
from .core.logger import setup_logging
from .middleware.logging import setup_middleware

app_settings = get_settings()

# 初始化日志系统
setup_logging()

# 获取日志器
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=" * 60, extra={"event": "app_startup"})
    logger.info("WeaveEye API 服务启动中...", extra={"event": "app_startup"})

    # startup: 连接 MongoDB
    logger.info("正在连接 MongoDB...")
    from .core.mongodb import connect_mongodb, close_mongodb

    await connect_mongodb()
    logger.info(
        "MongoDB 连接成功",
        extra={"event": "mongodb_connected", "uri": app_settings.mongodb_uri},
    )

    # startup: 启动分析看板快照调度器
    logger.info("启动分析看板调度器...")
    from .services.analytics_service import get_analytics_service

    analytics_service = get_analytics_service()
    analytics_service.start()
    logger.info("分析看板调度器已启动", extra={"event": "analytics_scheduler_started"})

    # startup: 启动数据同步调度器 (SIMS + MES)
    logger.info("启动数据同步调度器...")
    from .services.sync_scheduler_service import get_sync_scheduler_service

    sync_scheduler = get_sync_scheduler_service()
    sync_scheduler.start_scheduler()
    logger.info("数据同步调度器已启动", extra={"event": "sync_scheduler_started"})

    logger.info("=" * 60, extra={"event": "app_ready"})
    logger.info("WeaveEye API 服务启动完成 ✓")

    yield

    # shutdown: 先停同步调度器，再停分析看板，最后关 MongoDB
    logger.info("正在关闭服务...")
    logger.info("停止数据同步调度器...")
    await sync_scheduler.stop_scheduler()
    logger.info("停止分析看板调度器...")
    await analytics_service.stop()
    logger.info("关闭 MongoDB 连接...")
    await close_mongodb()
    logger.info("服务已关闭 ✓", extra={"event": "app_shutdown"})


app = FastAPI(
    title="WeaveEye API",
    description="智能诊断系统后端 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 注册中间件
setup_middleware(app)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器 - 记录异常并返回友好错误"""
    logger.exception(
        f"全局异常: {type(exc).__name__}",
        extra={
            "event": "global_exception",
            "method": request.method,
            "path": request.url.path,
            "exception": str(exc),
            "exception_type": type(exc).__name__,
        },
    )
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": str(exc), "message": "服务器内部错误"},
    )


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "WeaveEye API", "version": "1.0.0"}


# 注册路由
app.include_router(auth.router, prefix="/api")
app.include_router(diagnosis.router, prefix="/api")
app.include_router(error_logs.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
app.include_router(factories.router, prefix="/api")
app.include_router(knowledge_base.router, prefix="/api")


# 根路径
@app.get("/")
async def root():
    return {"message": "WeaveEye API Server", "docs": "/docs", "health": "/health"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=app_settings.host,
        port=app_settings.port,
        reload=app_settings.debug,
    )

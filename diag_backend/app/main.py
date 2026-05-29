from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .routers import analytics, diagnosis, error_logs, factories, knowledge_base, settings as settings_router, sync, auth
from .core.config import get_settings

app_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # startup: 连接 MongoDB
    from .core.mongodb import connect_mongodb, close_mongodb
    await connect_mongodb()

    # startup: 启动分析看板快照调度器
    from .services.analytics_service import get_analytics_service
    analytics_service = get_analytics_service()
    analytics_service.start()

    # startup: 启动数据同步调度器 (SIMS + MES)
    from .services.sync_scheduler_service import get_sync_scheduler_service
    sync_scheduler = get_sync_scheduler_service()
    sync_scheduler.start_scheduler()

    yield

    # shutdown: 先停同步调度器，再停分析看板，最后关 MongoDB
    await sync_scheduler.stop_scheduler()
    await analytics_service.stop()
    await close_mongodb()


app = FastAPI(
    title="WeaveEye API",
    description="智能诊断系统后端 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc),
            "message": "服务器内部错误"
        }
    )


# 健康检查
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "WeaveEye API",
        "version": "1.0.0"
    }


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
    return {
        "message": "WeaveEye API Server",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=app_settings.host,
        port=app_settings.port,
        reload=app_settings.debug
    )

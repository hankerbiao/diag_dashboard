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
from .core.lifespan import app_lifespan
from .middleware.logging import setup_middleware

app_settings = get_settings()
setup_logging()

logger = logging.getLogger(__name__)


app = FastAPI(
    title="WeaveEye API",
    description="智能诊断系统后端 API",
    version="1.0.0",
    lifespan=app_lifespan,
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

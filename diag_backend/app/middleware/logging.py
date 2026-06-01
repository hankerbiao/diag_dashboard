"""
请求日志中间件

功能：
- 自动生成 trace_id 并注入请求上下文
- 记录每个请求的完整生命周期
- 请求耗时统计
- 异常自动捕获和记录
"""

import time
import uuid
import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..core.logger import set_context, clear_context, generate_trace_id

logger = logging.getLogger("http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    # 不记录日志的路径
    EXCLUDED_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}

    # 敏感字段（脱敏处理）
    SENSITIVE_FIELDS = {
        "password",
        "token",
        "secret",
        "api_key",
        "authorization",
        "access_token",
        "refresh_token",
        "jwt",
        "old_password",
        "new_password",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成 trace_id
        trace_id = request.headers.get("X-Trace-ID") or generate_trace_id()
        request_id = str(uuid.uuid4())[:8]

        # 设置日志上下文
        set_context(
            trace_id=trace_id,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        # 记录请求开始
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "-")

        # 排除路径检查
        if request.url.path not in self.EXCLUDED_PATHS:
            logger.info(
                f"--> {request.method} {request.url.path}",
                extra={
                    "event": "request_start",
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "query_params": dict(request.query_params)
                    if request.query_params
                    else None,
                },
            )

        # 处理请求
        response: Response = None
        error: Exception = None
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            error = e
            raise
        finally:
            # 计算耗时
            duration_ms = (time.time() - start_time) * 1000

            # 获取响应状态码
            status_code = response.status_code if response else 500

            # 记录请求结束
            if request.url.path not in self.EXCLUDED_PATHS:
                log_data = {
                    "event": "request_end",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": client_ip,
                }

                # 添加响应头中的 trace_id
                if response:
                    response.headers["X-Trace-ID"] = trace_id
                    response.headers["X-Request-ID"] = request_id

                if error:
                    log_data["error"] = str(error)
                    log_data["error_type"] = type(error).__name__
                    logger.error(
                        f"<-- {request.method} {request.url.path} {status_code} {duration_ms:.2f}ms [ERROR]",
                        extra=log_data,
                    )
                elif status_code >= 400:
                    logger.warning(
                        f"<-- {request.method} {request.url.path} {status_code} {duration_ms:.2f}ms",
                        extra=log_data,
                    )
                else:
                    logger.info(
                        f"<-- {request.method} {request.url.path} {status_code} {duration_ms:.2f}ms",
                        extra=log_data,
                    )

            # 清除上下文
            clear_context()

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP"""
        # 优先从 X-Forwarded-For 获取
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # 其次从 X-Real-IP 获取
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # 最后从客户端地址获取
        if request.client:
            return request.client.host
        return "-"

    def _sanitize_params(self, params: dict) -> dict:
        """脱敏敏感参数"""
        sanitized = {}
        for key, value in params.items():
            if key.lower() in self.SENSITIVE_FIELDS:
                sanitized[key] = "***"
            else:
                sanitized[key] = value
        return sanitized


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """专门处理未捕获异常的中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception as e:
            logger.exception(
                f"Unhandled exception: {type(e).__name__}",
                extra={
                    "event": "unhandled_exception",
                    "method": request.method,
                    "path": request.url.path,
                    "exception": str(e),
                    "exception_type": type(e).__name__,
                },
            )
            raise


def setup_middleware(app) -> None:
    """注册中间件到应用"""
    # 注意：中间件按注册顺序反向执行
    app.add_middleware(ErrorLoggingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

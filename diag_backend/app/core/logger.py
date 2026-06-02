"""
统一日志系统

特性：
- 结构化日志（可选 JSON 格式）
- 请求链路追踪（trace_id）
- 日志轮转（文件输出时自动轮转）
- 彩色控制台输出（开发环境）
- 上下文信息注入（user_id, factory_id 等）
"""

import logging
import os
import sys
import json
import uuid
from logging.handlers import RotatingFileHandler
from typing import Any

from .config import get_settings
from .utils import utc_now_iso

# 全局上下文变量
_log_context: dict[str, Any] = {}


class TraceIdFilter(logging.Filter):
    """日志过滤器：添加 trace_id"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _log_context.get("trace_id", "-")
        return True


class ContextFilter(logging.Filter):
    """日志过滤器：添加上下文信息"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.user_id = _log_context.get("user_id", "-")
        record.factory_id = _log_context.get("factory_id", "-")
        record.job_id = _log_context.get("job_id", "-")
        record.request_id = _log_context.get("request_id", "-")
        return True


class ColoredFormatter(logging.Formatter):
    """彩色控制台格式化器"""

    COLORS = {
        "DEBUG": "\033[36m",  # 青色
        "INFO": "\033[32m",  # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",  # 红色
        "CRITICAL": "\033[35m",  # 紫色
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname_colored = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class JsonFormatter(logging.Formatter):
    """JSON 格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "time": utc_now_iso(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", "-"),
            "user_id": getattr(record, "user_id", "-"),
            "factory_id": getattr(record, "factory_id", "-"),
            "job_id": getattr(record, "job_id", "-"),
            "request_id": getattr(record, "request_id", "-"),
        }

        # 添加模块信息
        if hasattr(record, "module"):
            log_data["module"] = record.module

        # 添加函数名
        if hasattr(record, "funcName"):
            log_data["function"] = record.funcName

        # 添加行号
        if hasattr(record, "lineno"):
            log_data["line"] = record.lineno

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加额外字段
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data, ensure_ascii=False, default=str)


class SimpleFormatter(logging.Formatter):
    """简洁格式化器（生产环境控制台）"""

    def format(self, record: logging.LogRecord) -> str:
        trace_id = getattr(record, "trace_id", "-")
        trace_str = f"[{trace_id}]" if trace_id != "-" else ""
        return (
            f"{self.formatTime(record)} "
            f"[{record.levelname_colored if hasattr(record, 'levelname_colored') else record.levelname}] "
            f"{trace_str} "
            f"[{record.name}] "
            f"{record.getMessage()}"
        )


def _get_file_formatter() -> logging.Formatter:
    """获取文件日志格式化器"""
    settings = get_settings()
    if settings.log_json:
        return JsonFormatter()
    # 非 JSON 格式也用简洁格式
    fmt = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    return logging.Formatter(fmt, date_fmt)


def _get_console_formatter() -> logging.Formatter:
    """获取控制台日志格式化器"""
    settings = get_settings()
    if settings.log_format == "json":
        return JsonFormatter()
    fmt = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    return ColoredFormatter(fmt, date_fmt)


def setup_logging() -> None:
    """初始化日志系统"""
    settings = get_settings()

    # 清理现有 handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 设置根日志级别
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    console_handler.setFormatter(_get_console_formatter())
    console_handler.addFilter(TraceIdFilter())
    console_handler.addFilter(ContextFilter())
    root_logger.addHandler(console_handler)

    # 文件 Handler（可选）
    if settings.log_file:
        # 确保日志目录存在
        log_dir = settings.log_dir
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=settings.log_file,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        )
        file_handler.setFormatter(_get_file_formatter())
        file_handler.addFilter(TraceIdFilter())
        file_handler.addFilter(ContextFilter())
        root_logger.addHandler(file_handler)

    # 第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(
        logging.WARNING if not settings.log_sql else logging.DEBUG
    )

    logging.info(
        "日志系统初始化完成",
        extra={
            "log_level": settings.log_level,
            "log_format": settings.log_format,
            "log_file": settings.log_file or "console only",
        },
    )


def get_logger(name: str) -> logging.Logger:
    """获取带上下文的日志记录器"""
    return logging.getLogger(name)


def generate_trace_id() -> str:
    """生成新的 trace_id"""
    return str(uuid.uuid4())[:8]


def set_context(**kwargs) -> None:
    """设置日志上下文"""
    _log_context.update(kwargs)


def clear_context() -> None:
    """清除日志上下文"""
    _log_context.clear()


def get_context() -> dict[str, Any]:
    """获取当前日志上下文"""
    return _log_context.copy()


# 便捷函数：带上下文创建日志
class LoggerAdapter(logging.LoggerAdapter):
    """带上下文的日志适配器"""

    def process(self, msg: str, kwargs: dict) -> tuple:
        # 合并 extra 数据
        extra = kwargs.get("extra", {})
        extra.update(_log_context)
        kwargs["extra"] = extra
        return msg, kwargs


def get_contextual_logger(name: str) -> LoggerAdapter:
    """获取带上下文的日志适配器"""
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, _log_context)


# 快捷日志函数
def log_info(module: str, message: str, **kwargs) -> None:
    """快捷 Info 日志"""
    logger = get_logger(module)
    logger.info(message, extra=kwargs)


def log_warning(module: str, message: str, **kwargs) -> None:
    """快捷 Warning 日志"""
    logger = get_logger(module)
    logger.warning(message, extra=kwargs)


def log_error(module: str, message: str, exc_info: bool = False, **kwargs) -> None:
    """快捷 Error 日志"""
    logger = get_logger(module)
    logger.error(message, exc_info=exc_info, extra=kwargs)


def log_debug(module: str, message: str, **kwargs) -> None:
    """快捷 Debug 日志"""
    logger = get_logger(module)
    logger.debug(message, extra=kwargs)

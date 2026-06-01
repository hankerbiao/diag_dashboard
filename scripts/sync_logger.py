"""
同步脚本共享日志模块

提供统一的日志格式和配置，支持：
- 控制台彩色输出
- 文件输出（按日期轮转）
- 结构化日志格式（JSON）
"""
import os
import sys
import json
import logging
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler


# ══════════════════════════════════════════════════════════════════
# 日志配置
# ══════════════════════════════════════════════════════════════════
LOG_LEVEL = os.environ.get("SYNC_LOG_LEVEL", "INFO")
LOG_DIR = os.environ.get("SYNC_LOG_DIR", "./logs")
LOG_JSON = os.environ.get("SYNC_LOG_JSON", "false").lower() == "true"
TRACE_ID = str(uuid.uuid4())[:8]


# ══════════════════════════════════════════════════════════════════
# 日志格式化
# ══════════════════════════════════════════════════════════════════
class ColoredFormatter(logging.Formatter):
    """彩色控制台格式化器"""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        level = f"{color}{record.levelname}{self.RESET}"
        trace = getattr(record, "trace_id", TRACE_ID)

        return (
            f"{self.formatTime(record)} "
            f"[{level}] "
            f"[{trace}] "
            f"{record.getMessage()}"
        )


class JsonFormatter(logging.Formatter):
    """JSON 格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", TRACE_ID),
            "script": getattr(record, "script", "sync"),
        }

        # 添加上下文字段
        for field in ["factory_id", "job_id", "duration_ms", "count", "error"]:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


class SimpleFormatter(logging.Formatter):
    """简洁格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        trace = getattr(record, "trace_id", TRACE_ID)
        return (
            f"{self.formatTime(record)} "
            f"[{record.levelname}] "
            f"[{trace}] "
            f"{record.getMessage()}"
        )


def _get_formatter() -> logging.Formatter:
    """获取格式化器"""
    if LOG_JSON:
        return JsonFormatter()
    return ColoredFormatter()


# ══════════════════════════════════════════════════════════════════
# 日志器创建
# ══════════════════════════════════════════════════════════════════
def setup_logger(name: str = "sync") -> logging.Logger:
    """设置并返回日志器"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # 避免重复添加 handlers
    if logger.handlers:
        return logger

    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    console_handler.setFormatter(_get_formatter())
    logger.addHandler(console_handler)

    # 文件 Handler（可选）
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"sync_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=50 * 1024 * 1024, backupCount=30, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JsonFormatter() if LOG_JSON else SimpleFormatter())
    logger.addHandler(file_handler)

    return logger


# ══════════════════════════════════════════════════════════════════
# 便捷日志函数
# ══════════════════════════════════════════════════════════════════
def get_logger(name: str = "sync") -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(name) if logging.getLogger(name).handlers else setup_logger(name)


def log_sync_start(script: str, **kwargs):
    """记录同步开始"""
    logger = get_logger()
    extra = {"script": script, "event": "sync_start", **kwargs}
    logger.info(f"🔄 同步开始: {script}", extra=extra)


def log_sync_complete(script: str, duration_ms: float, **kwargs):
    """记录同步完成"""
    logger = get_logger()
    extra = {"script": script, "event": "sync_complete", "duration_ms": duration_ms, **kwargs}
    logger.info(f"✅ 同步完成: {script} ({duration_ms / 1000:.1f}s)", extra=extra)


def log_sync_error(script: str, error: str, **kwargs):
    """记录同步错误"""
    logger = get_logger()
    extra = {"script": script, "event": "sync_error", "error": error, **kwargs}
    logger.error(f"❌ 同步失败: {script} - {error}", extra=extra)


def log_factory_start(factory_id: str, **kwargs):
    """记录厂区同步开始"""
    logger = get_logger()
    extra = {"factory_id": factory_id, "event": "factory_start", **kwargs}
    logger.info(f"📥 厂区开始: {factory_id}", extra=extra)


def log_factory_complete(factory_id: str, servers: int, details: int, skipped: int = 0, duration_ms: float = 0, **kwargs):
    """记录厂区同步完成"""
    logger = get_logger()
    extra = {
        "factory_id": factory_id, "event": "factory_complete",
        "servers": servers, "details": details, "skipped": skipped,
        "duration_ms": duration_ms, **kwargs
    }
    logger.info(
        f"📥 厂区完成: {factory_id} | 服务器: {servers}台 | 详情: {details}条"
        + (f" | 跳过: {skipped}台" if skipped else "")
        + (f" | 耗时: {duration_ms / 1000:.1f}s" if duration_ms else ""),
        extra=extra
    )


def log_api_call(url: str, method: str = "POST", status_code: int = None, count: int = None, duration_ms: float = None, error: str = None):
    """记录 API 调用"""
    logger = get_logger()
    msg = f"🌐 API: {method} {url}"
    if status_code:
        msg += f" → {status_code}"
    if count is not None:
        msg += f" | 数据: {count}条"
    if duration_ms is not None:
        msg += f" | 耗时: {duration_ms:.0f}ms"
    if error:
        msg += f" | 错误: {error}"

    extra = {"url": url, "method": method, "status_code": status_code, "count": count, "duration_ms": duration_ms, "error": error}
    if status_code and 200 <= status_code < 300:
        logger.debug(msg, extra=extra)
    elif error:
        logger.error(msg, extra=extra)
    else:
        logger.info(msg, extra=extra)


def log_step(step: str, detail: str = "", count: int = None):
    """记录处理步骤"""
    logger = get_logger()
    msg = f"  └─ {step}"
    if detail:
        msg += f": {detail}"
    if count is not None:
        msg += f" ({count})"
    logger.debug(msg, extra={"step": step, "detail": detail, "count": count})


def log_progress(current: int, total: int, prefix: str = "", suffix: str = ""):
    """记录进度"""
    logger = get_logger()
    pct = (current / total * 100) if total > 0 else 0
    msg = f"  {prefix}{current}/{total} ({pct:.0f}%){suffix}"
    logger.debug(msg)


def log_data_stats(inserted: int = 0, updated: int = 0, skipped: int = 0, failed: int = 0, total: int = 0):
    """记录数据统计"""
    logger = get_logger()
    parts = []
    if inserted > 0:
        parts.append(f"新增: {inserted}")
    if updated > 0:
        parts.append(f"更新: {updated}")
    if skipped > 0:
        parts.append(f"跳过: {skipped}")
    if failed > 0:
        parts.append(f"失败: {failed}")

    msg = f"📊 数据统计: {', '.join(parts)}" if parts else f"📊 数据统计: {total}条"
    logger.info(msg, extra={"inserted": inserted, "updated": updated, "skipped": skipped, "failed": failed, "total": total})


def log_warning(msg: str, **kwargs):
    """记录警告"""
    logger = get_logger()
    logger.warning(f"⚠️  {msg}", extra=kwargs)


def log_debug(msg: str, **kwargs):
    """记录调试信息"""
    logger = get_logger()
    logger.debug(msg, extra=kwargs)


class SyncTimer:
    """同步计时器上下文管理器"""

    def __init__(self, name: str, logger_name: str = "sync"):
        self.name = name
        self.logger = get_logger(logger_name)
        self.start_time: float = 0
        self.duration_ms: float = 0

    def __enter__(self):
        self.start_time = datetime.now().timestamp() * 1000
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = datetime.now().timestamp() * 1000 - self.start_time
        if exc_type:
            log_sync_error(self.name, str(exc_val))
        else:
            log_sync_complete(self.name, self.duration_ms)
        return False
"""Shared utility functions"""
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_FAIL_HINTS = ("失败", "fail", "failed", "ng", "error", "不通过", "未通过", "不合格", "异常", "超时", "abort")
_PASS_HINTS = ("成功", "pass", "passed", "ok")


def is_test_passed(result: str) -> bool:
    """SIMS server_test_result 是否为通过（与看板/异常看板判定一致）。"""
    if not result or not str(result).strip():
        return False
    lower = str(result).strip().lower()
    if any(k in lower for k in _FAIL_HINTS):
        return False
    return any(k in lower for k in _PASS_HINTS) or "通过" in lower


def is_test_failed(result: str) -> bool:
    """SIMS server_test_result 是否为失败。"""
    if not result or not str(result).strip():
        return False
    if is_test_passed(result):
        return False
    lower = str(result).strip().lower()
    return any(k in lower for k in _FAIL_HINTS)


def is_sims_record_failed(record: dict) -> bool:
    """判断 SIMS 单条测试明细是否为失败（含结果字段与故障类型启发）。"""
    status = (
        (record.get("server_test_result") or record.get("fail_details") or record.get("decision") or "")
        .strip()
    )
    if is_test_failed(status):
        return True
    if is_test_passed(status):
        return False
    faults = (
        record.get("fault_type1"),
        record.get("fault_type2"),
        record.get("fault_type3"),
    )
    if any(f and str(f).strip() for f in faults):
        return True
    return False


def validate_log_path(log_path: str) -> str:
    """校验相对日志路径，防止 SSRF / 路径遍历。"""
    path = (log_path or "").strip()
    if not path:
        raise ValueError("日志路径不能为空")
    if "://" in path or path.startswith(("/", "\\")) or ".." in path.split("/"):
        raise ValueError("无效的日志路径")
    return path


def parse_object_id(doc_id: str) -> ObjectId:
    """Parse string to ObjectId, raise HTTPException if invalid"""
    try:
        return ObjectId(doc_id)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 ID 格式")



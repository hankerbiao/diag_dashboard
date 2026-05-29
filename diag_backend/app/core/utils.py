"""Shared utility functions to avoid code duplication"""
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, TypeVar, Optional
from bson import ObjectId
from fastapi import HTTPException

T = TypeVar('T')


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_object_id(doc_id: str) -> ObjectId:
    """Parse string to ObjectId, raise HTTPException if invalid"""
    try:
        return ObjectId(doc_id)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 ID 格式")


def singleton(cls: type[T]) -> Callable[[], T]:
    """Singleton decorator for service classes"""
    _instance: Optional[T] = None

    @wraps(cls)
    def get_instance() -> T:
        nonlocal _instance
        if _instance is None:
            _instance = cls()
        return _instance

    return get_instance
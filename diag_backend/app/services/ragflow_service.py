"""
RAGFlow 服务封装 — 知识库管理、文档解析、检索问答

RAGFlow 配置可选。未配置时所有操作返回空/失败，不影响服务启动。
"""
import logging
from typing import Optional

import httpx

from ..core.config import get_settings

logger = logging.getLogger(__name__)

RAGFLOW_DEFAULT_DATASET_NAME = "weaveeye-knowledge-base"
RAGFLOW_STATUS_MAP = {
    "UNSTART": "queued",
    "RUNNING": "parsing",
    "DONE": "parsed",
    "FAIL": "failed",
}


def _get_credentials() -> tuple[str, str]:
    s = get_settings()
    return s.ragflow_api_url.rstrip("/") if s.ragflow_api_url else "", s.ragflow_api_key or ""


def _is_configured() -> bool:
    url, key = _get_credentials()
    return bool(url and key)


def _headers() -> dict:
    _, key = _get_credentials()
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _check(resp: httpx.Response) -> dict:
    """统一检查 RAGFlow API 响应，返回 data 字段"""
    try:
        body = resp.json()
    except Exception:
        logger.error("RAGFlow response not JSON: %s", resp.text[:500])
        raise RuntimeError(f"RAGFlow 返回异常: {resp.status_code}")

    code = body.get("code", -1)
    if code != 0:
        msg = body.get("message", body.get("msg", "未知错误"))
        logger.error("RAGFlow API error [%s]: %s", code, msg)
        raise RuntimeError(f"RAGFlow 错误: {msg}")

    return body.get("data", {})


# ════════════════════════════════════════════════════════════
# 1. Dataset — 知识库管理
# ════════════════════════════════════════════════════════════


async def list_datasets(
    page: int = 1,
    page_size: int = 100,
) -> list[dict]:
    """获取知识库列表 (GET /api/v1/datasets)"""
    if not _is_configured():
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_get_credentials()[0]}/api/v1/datasets",
            params={"page": page, "page_size": page_size},
            headers=_headers(),
        )
        data = _check(resp)
        return data if isinstance(data, list) else data.get("items", [])


async def create_dataset(
    name: str,
    description: str = "",
) -> dict:
    """创建知识库 (POST /api/v1/datasets)"""
    if not _is_configured():
        return {}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_get_credentials()[0]}/api/v1/datasets",
            headers=_headers(),
            json={"name": name, "description": description},
        )
        return _check(resp)


async def delete_dataset(dataset_id: str) -> bool:
    """删除知识库 (DELETE /api/v1/datasets)"""
    if not _is_configured():
        return False
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.request(
            "DELETE",
            f"{_get_credentials()[0]}/api/v1/datasets",
            headers=_headers(),
            json={"ids": [dataset_id]},
        )
        _check(resp)
        return True


# ════════════════════════════════════════════════════════════
# 2. Document — 文档管理与解析
# ════════════════════════════════════════════════════════════


async def upload_document(
    dataset_id: str,
    file_path: str,
    file_name: str,
) -> dict:
    """上传文档到知识库 (POST /api/v1/datasets/{dataset_id}/documents)

    返回: {"id": "...", "name": "...", "status": "UNSTART", ...}
    """
    if not _is_configured():
        return {}
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    url, _ = _get_credentials()
    async with httpx.AsyncClient(timeout=120) as client:
        with open(file_path, "rb") as f:
            files = {"file": (file_name, f, "application/octet-stream")}
            resp = await client.post(
                f"{url}/api/v1/datasets/{dataset_id}/documents",
                headers={"Authorization": _headers()["Authorization"]},
                files=files,
            )
        data = _check(resp)
        return data[0] if isinstance(data, list) and data else data


async def run_parsing(
    dataset_id: str,
    document_ids: list[str],
) -> bool:
    """触发文档解析 (POST /api/v1/datasets/{dataset_id}/chunks)"""
    if not _is_configured() or not document_ids:
        return True

    url, _ = _get_credentials()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{url}/api/v1/datasets/{dataset_id}/chunks",
            headers=_headers(),
            json={"document_ids": document_ids},
        )
        _check(resp)
        return True


async def list_documents(
    dataset_id: str,
    page: int = 1,
    page_size: int = 100,
) -> list[dict]:
    """查询知识库中文档列表及状态 (GET /api/v1/datasets/{dataset_id}/documents)"""
    if not _is_configured():
        return []
    url, _ = _get_credentials()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{url}/api/v1/datasets/{dataset_id}/documents",
            params={
                "page": page,
                "page_size": page_size,
            },
            headers=_headers(),
        )
        data = _check(resp)
        if isinstance(data, list):
            return data
        return data.get("docs", data.get("items", []))


async def get_document_status(
    dataset_id: str,
    document_id: str,
) -> str:
    """查询单个文档解析状态

    返回: "UNSTART" | "RUNNING" | "DONE" | "FAIL"
    """
    docs = await list_documents(dataset_id, page_size=1000)
    for doc in docs:
        if doc.get("id") == document_id:
            return doc.get("run", "UNSTART")
    return "UNSTART"


async def delete_document(
    dataset_id: str,
    document_id: str,
) -> bool:
    """从知识库删除文档 (DELETE /api/v1/datasets/{dataset_id}/documents)"""
    if not _is_configured():
        return False
    url, _ = _get_credentials()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.request(
            "DELETE",
            f"{url}/api/v1/datasets/{dataset_id}/documents",
            headers=_headers(),
            json={"ids": [document_id]},
        )
        _check(resp)
        return True


# ════════════════════════════════════════════════════════════
# 3. Chat — 检索与问答推理 (预留)
# ════════════════════════════════════════════════════════════


async def create_session(dataset_ids: list[str]) -> dict:
    """创建检索会话 (POST /api/v1/conversation)"""
    if not _is_configured():
        return {}
    url, _ = _get_credentials()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{url}/api/v1/conversation",
            headers=_headers(),
            json={"dataset_ids": dataset_ids},
        )
        return _check(resp)


async def send_message(
    session_id: str,
    question: str,
    stream: bool = False,
) -> dict:
    """发送问答消息 (POST /api/v1/conversation/completion)"""
    if not _is_configured():
        return {}
    url, _ = _get_credentials()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{url}/api/v1/conversation/completion",
            headers=_headers(),
            json={
                "conversation_id": session_id,
                "question": question,
                "stream": stream,
            },
        )
        return _check(resp)


# ════════════════════════════════════════════════════════════
# 状态映射工具
# ════════════════════════════════════════════════════════════

_default_dataset_id: Optional[str] = None


async def resolve_default_dataset() -> str:
    """获取或自动创建默认知识库，返回 dataset_id"""
    if not _is_configured():
        return ""

    global _default_dataset_id
    if _default_dataset_id:
        return _default_dataset_id

    datasets = await list_datasets(page_size=200)
    for ds in datasets:
        if ds.get("name") == RAGFLOW_DEFAULT_DATASET_NAME:
            _default_dataset_id = ds.get("id")
            return _default_dataset_id

    result = await create_dataset(
        name=RAGFLOW_DEFAULT_DATASET_NAME,
        description="WeaveEye 智能诊断系统默认知识库",
    )
    _default_dataset_id = result.get("id")
    return _default_dataset_id


def map_status(ragflow_status: str) -> str:
    """将 RAGFlow 状态转为系统内部状态"""
    return RAGFLOW_STATUS_MAP.get(ragflow_status, "queued")

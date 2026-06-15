"""RAGFlow 服务封装 — 知识库管理、文档解析、检索问答"""
import logging
from typing import Optional
import httpx
from contextlib import asynccontextmanager

from ..core.config import get_settings

logger = logging.getLogger(__name__)

RAGFLOW_DEFAULT_DATASET_NAME = "weaveeye-knowledge-base"
RAGFLOW_DEFAULT_CHAT_NAME = "WeaveEye-Diagnosis"
RAGFLOW_STATUS_MAP = {"UNSTART": "queued", "RUNNING": "parsing", "DONE": "parsed", "FAIL": "failed"}

# 超时配置
T_SHORT, T_MEDIUM, T_LONG = 15, 30, 120

_url: Optional[str] = None
_key: Optional[str] = None


def _cfg() -> tuple[str, str]:
    global _url, _key
    if _url is None:
        s = get_settings()
        _url = s.ragflow_api_url.rstrip("/") if s.ragflow_api_url else ""
        _key = s.ragflow_api_key or ""
    return _url, _key


def _ok() -> bool:
    url, key = _cfg()
    return bool(url and key)


def _hdrs() -> dict:
    return {"Authorization": f"Bearer {_cfg()[1]}", "Content-Type": "application/json"}


@asynccontextmanager
async def _client(timeout: int = T_SHORT):
    if not _ok():
        logger.debug("RAGFlow _client: 未配置，返回 None")
        yield None
        return
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            yield c
    except Exception as e:
        logger.debug("RAGFlow _client HTTP 异常", extra={"error": str(e), "error_type": type(e).__name__, "timeout": timeout}, exc_info=True)
        raise


def _check(resp: httpx.Response) -> dict:
    try:
        body = resp.json()
    except Exception:
        raise RuntimeError(f"RAGFlow 返回异常: {resp.status_code}")
    if body.get("code", -1) != 0:
        msg = body.get("message", body.get("msg", "未知错误"))
        raise RuntimeError(f"RAGFlow 错误: {msg}")
    return body.get("data", {})


# ── Dataset ──

async def list_datasets(page: int = 1, page_size: int = 100) -> list[dict]:
    if not _ok():
        return []
    async with _client() as c:
        resp = await c.get(f"{_cfg()[0]}/api/v1/datasets", params={"page": page, "page_size": page_size}, headers=_hdrs())
        data = _check(resp)
        return data if isinstance(data, list) else data.get("items", [])


async def create_dataset(name: str, description: str = "") -> dict:
    if not _ok():
        return {}
    async with _client() as c:
        resp = await c.post(f"{_cfg()[0]}/api/v1/datasets", headers=_hdrs(), json={"name": name, "description": description})
        return _check(resp)


async def delete_dataset(dataset_id: str) -> bool:
    if not _ok():
        return False
    async with _client() as c:
        await c.request("DELETE", f"{_cfg()[0]}/api/v1/datasets", headers=_hdrs(), json={"ids": [dataset_id]})
        _check(c.response)
        return True


# ── Document ──

async def upload_document(dataset_id: str, file_path: str, file_name: str) -> dict:
    if not _ok():
        return {}
    from pathlib import Path
    if not Path(file_path).exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    async with _client(T_LONG) as c:
        with open(file_path, "rb") as f:
            resp = await c.post(f"{_cfg()[0]}/api/v1/datasets/{dataset_id}/documents",
                                headers={"Authorization": _hdrs()["Authorization"]},
                                files={"file": (file_name, f, "application/octet-stream")})
        data = _check(resp)
        return data[0] if isinstance(data, list) and data else data


async def run_parsing(dataset_id: str, document_ids: list[str]) -> bool:
    if not _ok() or not document_ids:
        return True
    async with _client(T_MEDIUM) as c:
        resp = await c.post(f"{_cfg()[0]}/api/v1/datasets/{dataset_id}/chunks", headers=_hdrs(), json={"document_ids": document_ids})
        _check(resp)
        return True


async def list_documents(dataset_id: str, page: int = 1, page_size: int = 100) -> list[dict]:
    if not _ok():
        return []
    async with _client() as c:
        resp = await c.get(f"{_cfg()[0]}/api/v1/datasets/{dataset_id}/documents", params={"page": page, "page_size": page_size}, headers=_hdrs())
        data = _check(resp)
        return data if isinstance(data, list) else data.get("docs", data.get("items", []))


async def get_document_status(dataset_id: str, document_id: str) -> str:
    docs = await list_documents(dataset_id, page_size=1000)
    for doc in docs:
        if doc.get("id") == document_id:
            return doc.get("run", "UNSTART")
    return "UNSTART"


async def delete_document(dataset_id: str, document_id: str) -> bool:
    if not _ok():
        return False
    async with _client() as c:
        resp = await c.request("DELETE", f"{_cfg()[0]}/api/v1/datasets/{dataset_id}/documents", headers=_hdrs(), json={"ids": [document_id]})
        _check(resp)
        return True


# ── Chat / Retrieval ──

async def list_chats(page: int = 1, page_size: int = 100) -> list[dict]:
    if not _ok():
        return []
    async with _client() as c:
        resp = await c.get(f"{_cfg()[0]}/api/v1/chats", params={"page": page, "page_size": page_size}, headers=_hdrs())
        data = _check(resp)
        return data.get("chats", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])


async def create_chat(name: str, dataset_ids: list[str]) -> dict:
    if not _ok():
        return {}
    async with _client() as c:
        resp = await c.post(f"{_cfg()[0]}/api/v1/chats", headers=_hdrs(), json={"name": name, "dataset_ids": dataset_ids})
        return _check(resp)


async def update_chat(chat_id: str, dataset_ids: list[str]) -> dict:
    if not _ok():
        return {}
    async with _client() as c:
        resp = await c.put(f"{_cfg()[0]}/api/v1/chats/{chat_id}", headers=_hdrs(), json={"dataset_ids": dataset_ids})
        return _check(resp)


async def get_chat(chat_id: str) -> dict:
    if not _ok():
        return {}
    for c in await list_chats(page_size=200):
        if c.get("id") == chat_id:
            return c
    return {}


async def search_knowledge_base(
    question: str, similarity_threshold: float = 0.2, vector_similarity_weight: float = 0.3, top_k: int = 10,
) -> dict:
    """检索知识库 — 使用 RAGFlow retrieval API"""
    logger.debug(
        "RAGFlow search_knowledge_base 开始",
        extra={"question": question[:200], "similarity_threshold": similarity_threshold, "top_k": top_k},
    )
    if not _ok():
        url, key = _cfg()
        logger.debug(
            "RAGFlow 未配置，跳过检索",
            extra={"ragflow_api_url_set": bool(url), "ragflow_api_key_set": bool(key)},
        )
        return {"references": []}
    dataset_id = await resolve_default_dataset()
    if not dataset_id:
        logger.debug("RAGFlow 默认数据集未找到，跳过检索")
        return {"references": []}

    logger.debug("RAGFlow 开始请求 retrieval API", extra={"dataset_id": dataset_id, "url": _cfg()[0]})
    try:
        async with _client(T_MEDIUM) as c:
            if c is None:
                logger.debug("RAGFlow HTTP 客户端创建失败 (_client 返回 None)")
                return {"references": []}
            resp = await c.post(f"{_cfg()[0]}/api/v1/retrieval", headers=_hdrs(), json={
                "question": question, "dataset_ids": [dataset_id],
                "similarity_threshold": similarity_threshold, "vector_similarity_weight": vector_similarity_weight, "top_k": top_k,
            })
            logger.debug(
                "RAGFlow retrieval API 响应",
                extra={"status_code": resp.status_code, "body_preview": resp.text[:500]},
            )
            result = resp.json()
            if result.get("code", -1) != 0:
                err_msg = f"RAGFlow 检索错误: {result.get('message', result.get('msg', '未知错误'))}"
                logger.debug("RAGFlow retrieval API 返回业务错误", extra={"code": result.get("code"), "message": result.get("message"), "msg": result.get("msg")})
                raise RuntimeError(err_msg)

            data = result.get("data", {})
            chunks = data.get("chunks", [])
            doc_map = {d.get("doc_id", ""): d.get("doc_name", "") for d in data.get("doc_aggs", []) if d.get("doc_id")}
            logger.debug("RAGFlow 检索成功", extra={"chunks_count": len(chunks), "docs_count": len(doc_map)})
    except Exception as e:
        logger.debug("RAGFlow search_knowledge_base 异常", extra={"error": str(e), "error_type": type(e).__name__}, exc_info=True)
        raise

    return {"references": [{
        "chunk_id": c.get("id", ""), "content": c.get("content", ""),
        "similarity": c.get("similarity", c.get("vector_similarity", 0.0)),
        "doc_name": doc_map.get(c.get("document_id", ""), ""),
    } for c in chunks]}


async def chat_completion(chat_id: str, question: str, stream: bool = False) -> dict:
    if not _ok():
        return {}
    chat_info = await get_chat(chat_id)
    async with _client(T_LONG) as c:
        body = {"messages": [{"role": "user", "content": question}], "stream": stream, "extra_body": {"reference": True}}
        if chat_info.get("llm_id"):
            body["model"] = chat_info["llm_id"]
        resp = await c.post(f"{_cfg()[0]}/api/v1/openai/{chat_id}/chat/completions", headers=_hdrs(), json=body)
        result = resp.json()
        if result.get("code", -1) != 0:
            raise RuntimeError(f"RAGFlow 对话错误: {result.get('message', result.get('msg', '未知错误'))}")
        return result


# ── 默认资源解析 ──

_default_dataset_id: Optional[str] = None
_default_chat_id: Optional[str] = None


async def resolve_default_dataset() -> str:
    global _default_dataset_id
    if not _ok() or _default_dataset_id:
        logger.debug("resolve_default_dataset: 使用缓存或未配置", extra={"_ok": _ok() if not _default_dataset_id else True, "cached_id": _default_dataset_id})
        return _default_dataset_id or ""

    cfg_name = get_settings().ragflow_default_dataset or RAGFLOW_DEFAULT_DATASET_NAME
    logger.debug("resolve_default_dataset: 开始查找数据集", extra={"dataset_name": cfg_name})
    datasets = await list_datasets(page_size=200)
    logger.debug("resolve_default_dataset: 获取到数据集列表", extra={"count": len(datasets)})
    for ds in datasets:
        if ds.get("name") == cfg_name:
            _default_dataset_id = ds.get("id")
            logger.debug("resolve_default_dataset: 找到数据集", extra={"dataset_id": _default_dataset_id, "name": cfg_name})
            return _default_dataset_id

    logger.debug("resolve_default_dataset: 数据集不存在，尝试创建", extra={"name": cfg_name})
    result = await create_dataset(name=cfg_name, description="WeaveEye 智能诊断系统默认知识库")
    _default_dataset_id = result.get("id")
    logger.debug("resolve_default_dataset: 创建结果", extra={"result": str(result)[:300], "dataset_id": _default_dataset_id})
    return _default_dataset_id


async def resolve_default_chat() -> str:
    global _default_chat_id
    if not _ok() or _default_chat_id:
        return _default_chat_id or ""

    dataset_id = await resolve_default_dataset()
    if not dataset_id:
        return ""

    for c in await list_chats(page_size=200):
        if c.get("name") == RAGFLOW_DEFAULT_CHAT_NAME:
            _default_chat_id = c.get("id")
            if dataset_id not in c.get("dataset_ids", []):
                await update_chat(_default_chat_id, [dataset_id])
            return _default_chat_id

    result = await create_chat(name=RAGFLOW_DEFAULT_CHAT_NAME, dataset_ids=[dataset_id])
    _default_chat_id = result.get("id")
    return _default_chat_id


def map_status(ragflow_status: str) -> str:
    return RAGFLOW_STATUS_MAP.get(ragflow_status, "queued")
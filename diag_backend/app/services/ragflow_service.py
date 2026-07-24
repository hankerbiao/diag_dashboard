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
RAGFLOW_KNOWLEDGE_TYPE_DESCRIPTIONS = {
    "troubleshooting": "WeaveEye 故障排查知识库",
    "repair_case": "WeaveEye 维修案例知识库",
    "operation_guide": "WeaveEye 操作规范知识库",
    "faq": "WeaveEye 常见问答知识库",
}

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
    except httpx.HTTPError as e:
        logger.warning(
            "RAGFlow HTTP 请求失败: %s",
            e,
            extra={"error_type": type(e).__name__, "timeout": timeout},
        )
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
    dataset_ids = await resolve_retrieval_dataset_ids()
    if not dataset_ids:
        logger.debug("RAGFlow 检索数据集未找到，跳过检索")
        return {"references": []}

    logger.debug(
        "RAGFlow 开始请求 retrieval API",
        extra={"dataset_ids": dataset_ids, "dataset_count": len(dataset_ids), "url": _cfg()[0]},
    )
    try:
        async with _client(T_MEDIUM) as c:
            if c is None:
                logger.debug("RAGFlow HTTP 客户端创建失败 (_client 返回 None)")
                return {"references": []}
            resp = await c.post(f"{_cfg()[0]}/api/v1/retrieval", headers=_hdrs(), json={
                "question": question, "dataset_ids": dataset_ids,
                "similarity_threshold": similarity_threshold, "vector_similarity_weight": vector_similarity_weight, "top_k": top_k,
            })
            logger.debug(
                "RAGFlow retrieval API 响应",
                extra={"status_code": resp.status_code, "body_preview": resp.text[:500]},
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code", -1) != 0:
                detail = result.get("message", result.get("msg", "未知错误"))
                logger.warning(
                    "RAGFlow retrieval API 返回业务错误: code=%s, detail=%s",
                    result.get("code"),
                    detail,
                )
                return {
                    "references": [],
                    "warning": f"知识库检索暂不可用: {detail}",
                }

            data = result.get("data", {})
            chunks = data.get("chunks", [])
            doc_map = {d.get("doc_id", ""): d.get("doc_name", "") for d in data.get("doc_aggs", []) if d.get("doc_id")}
            logger.debug("RAGFlow 检索成功", extra={"chunks_count": len(chunks), "docs_count": len(doc_map)})
    except httpx.HTTPError as e:
        return {"references": [], "warning": f"知识库连接失败: {e}"}
    except (AttributeError, TypeError, ValueError) as e:
        logger.warning("RAGFlow retrieval API 响应解析失败: %s", e)
        return {"references": [], "warning": "知识库返回了无法解析的响应"}

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
_dataset_ids_by_name: dict[str, str] = {}


def knowledge_dataset_names() -> dict[str, str]:
    """返回知识类型对应的数据集名称，允许通过环境变量覆盖。"""
    settings = get_settings()
    return {
        "troubleshooting": settings.ragflow_troubleshooting_dataset,
        "repair_case": settings.ragflow_repair_case_dataset,
        "operation_guide": settings.ragflow_operation_guide_dataset,
        "faq": settings.ragflow_faq_dataset,
    }


async def resolve_dataset(dataset_name: str, description: str = "") -> str:
    """按名称解析数据集，不存在时创建，并缓存其 ID。"""
    normalized_name = dataset_name.strip()
    if not _ok() or not normalized_name:
        return ""
    cached_id = _dataset_ids_by_name.get(normalized_name)
    if cached_id:
        return cached_id

    datasets = await list_datasets(page_size=200)
    for dataset in datasets:
        if dataset.get("name") == normalized_name and dataset.get("id"):
            dataset_id = str(dataset["id"])
            _dataset_ids_by_name[normalized_name] = dataset_id
            return dataset_id

    result = await create_dataset(name=normalized_name, description=description)
    dataset_id = str(result.get("id") or "")
    if dataset_id:
        _dataset_ids_by_name[normalized_name] = dataset_id
    return dataset_id


async def resolve_default_dataset() -> str:
    global _default_dataset_id
    if not _ok() or _default_dataset_id:
        logger.debug("resolve_default_dataset: 使用缓存或未配置", extra={"_ok": _ok() if not _default_dataset_id else True, "cached_id": _default_dataset_id})
        return _default_dataset_id or ""

    dataset_name = get_settings().ragflow_default_dataset or RAGFLOW_DEFAULT_DATASET_NAME
    _default_dataset_id = await resolve_dataset(
        dataset_name,
        description="WeaveEye 智能诊断系统默认知识库",
    )
    logger.debug(
        "resolve_default_dataset: 解析完成",
        extra={"dataset_name": dataset_name, "dataset_id": _default_dataset_id},
    )
    return _default_dataset_id


async def resolve_knowledge_dataset(knowledge_type: str = "") -> str:
    """按知识类型选择上传数据集；未指定类型时回退默认数据集。"""
    normalized_type = knowledge_type.strip()
    dataset_name = knowledge_dataset_names().get(normalized_type, "")
    if not dataset_name:
        return await resolve_default_dataset()
    return await resolve_dataset(
        dataset_name,
        description=RAGFLOW_KNOWLEDGE_TYPE_DESCRIPTIONS[normalized_type],
    )


async def resolve_retrieval_dataset_ids() -> list[str]:
    """解析检索使用的默认数据集和所有已经创建的类型数据集。"""
    default_id = await resolve_default_dataset()
    dataset_ids = [default_id] if default_id else []
    configured_names = set(knowledge_dataset_names().values())
    for dataset in await list_datasets(page_size=200):
        dataset_id = str(dataset.get("id") or "")
        dataset_name = str(dataset.get("name") or "")
        if dataset_id and dataset_name in configured_names and dataset_id not in dataset_ids:
            _dataset_ids_by_name[dataset_name] = dataset_id
            dataset_ids.append(dataset_id)
    return dataset_ids


async def resolve_default_chat() -> str:
    global _default_chat_id
    if not _ok() or _default_chat_id:
        return _default_chat_id or ""

    dataset_ids = await resolve_retrieval_dataset_ids()
    if not dataset_ids:
        return ""

    for c in await list_chats(page_size=200):
        if c.get("name") == RAGFLOW_DEFAULT_CHAT_NAME:
            _default_chat_id = c.get("id")
            if set(dataset_ids) != set(c.get("dataset_ids", [])):
                await update_chat(_default_chat_id, dataset_ids)
            return _default_chat_id

    result = await create_chat(name=RAGFLOW_DEFAULT_CHAT_NAME, dataset_ids=dataset_ids)
    _default_chat_id = result.get("id")
    return _default_chat_id


def map_status(ragflow_status: str) -> str:
    return RAGFLOW_STATUS_MAP.get(ragflow_status, "queued")

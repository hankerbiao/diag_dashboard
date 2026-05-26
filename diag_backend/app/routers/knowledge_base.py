"""
知识库管理路由 — 本地存储 + RAGFlow 自动同步
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException

from ..core.auth import get_current_user
from ..core.config import get_settings
from ..core.mongodb import get_collection
from ..models.request import KnowledgeDocUpdateRequest
from ..models.response import ApiResponse, KnowledgeDocResponse
from ..services import ragflow_service

logger = logging.getLogger(__name__)

ALLOWED_FORMATS = {"pdf", "docx", "md", "txt", "pptx", "xlsx", "csv", "html", "json", "xml"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

router = APIRouter(prefix="/knowledge-base", tags=["知识库"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_storage_dir() -> str:
    settings = get_settings()
    path = settings.knowledge_base_storage_path
    os.makedirs(path, exist_ok=True)
    return path


def _doc_response(doc: dict) -> KnowledgeDocResponse:
    return KnowledgeDocResponse(
        id=str(doc.get("_id")) if "_id" in doc else doc.get("id", ""),
        title=doc.get("title", ""),
        description=doc.get("description", ""),
        format=doc.get("format", ""),
        size_bytes=doc.get("size_bytes", 0),
        status=doc.get("status", "ready"),
        tags=doc.get("tags", []),
        uploaded_at=doc.get("uploaded_at"),
    )


# ════════════════════════════════════════════════════
# 上传文档
# ════════════════════════════════════════════════════

@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(""),
    tags: Optional[str] = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """上传知识库文档 — 本地存储 + RAGFlow 自动同步"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    if ext not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: .{ext}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小超过限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)")

    doc_title = (title or "").strip() or file.filename.rsplit(".", 1)[0]
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]

    # 本地存储
    storage_dir = _get_storage_dir()
    file_id = uuid.uuid4().hex
    saved_name = f"{file_id}.{ext}"
    file_path = os.path.join(storage_dir, saved_name)
    with open(file_path, "wb") as f:
        f.write(contents)

    now = _now_iso()
    doc: dict = {
        "title": doc_title,
        "description": (description or "").strip(),
        "format": ext,
        "size_bytes": len(contents),
        "file_path": file_path,
        "file_id": file_id,
        "status": "ready",
        "tags": tag_list,
        "user_id": current_user.get("user_id", ""),
        "uploaded_at": now,
        "ragflow_dataset_id": "",
        "ragflow_doc_id": "",
    }

    # 写入 MongoDB
    col = get_collection("knowledge_documents")
    result = await col.insert_one(doc)
    doc["_id"] = result.inserted_id

    # 同步到 RAGFlow
    dataset_id = await ragflow_service.resolve_default_dataset()
    rf_resp = await ragflow_service.upload_document(
        dataset_id=dataset_id,
        file_path=file_path,
        file_name=file.filename,
    )
    rf_doc_id = rf_resp.get("id", "")
    if rf_doc_id:
        await col.update_one(
            {"_id": result.inserted_id},
            {
                "$set": {
                    "ragflow_dataset_id": dataset_id,
                    "ragflow_doc_id": rf_doc_id,
                    "status": "queued",
                }
            },
        )
        doc["ragflow_dataset_id"] = dataset_id
        doc["ragflow_doc_id"] = rf_doc_id
        doc["status"] = "queued"

        # 触发解析
        await ragflow_service.run_parsing(
            dataset_id=dataset_id,
            document_ids=[rf_doc_id],
        )

        # 查询 RAGFlow 真实状态（解析触发后可能立即变为 RUNNING）
        actual_status = await ragflow_service.get_document_status(dataset_id, rf_doc_id)
        new_status = ragflow_service.map_status(actual_status)
        await col.update_one(
            {"_id": result.inserted_id},
            {"$set": {"status": new_status}},
        )
        doc["status"] = new_status

    return ApiResponse(success=True, data=_doc_response(doc).model_dump())


# ════════════════════════════════════════════════════
# 查询文档列表
# ════════════════════════════════════════════════════

@router.get("/documents")
async def list_documents(
    search: Optional[str] = Query(None, description="标题搜索关键词"),
    format: Optional[str] = Query(None, description="文件格式过滤"),
    tag: Optional[str] = Query(None, description="标签过滤"),
    sync_status: bool = Query(False, description="是否从 RAGFlow 同步解析状态"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """查询知识库文档列表（可选同步 RAGFlow 状态）"""
    col = get_collection("knowledge_documents")
    query: dict = {}
    if search:
        query["title"] = {"$regex": search, "$options": "i"}
    if format:
        query["format"] = format
    if tag:
        query["tags"] = tag

    total = await col.count_documents(query)
    skip = (page - 1) * limit
    cursor = col.find(query).sort("uploaded_at", -1).skip(skip).limit(limit)
    items_raw = await cursor.to_list(length=limit)

    # 惰性状态同步：对 parsing/queued 的文档查询 RAGFlow 最新状态
    if sync_status:
        for item in items_raw:
            rf_doc_id = item.get("ragflow_doc_id", "")
            rf_dataset_id = item.get("ragflow_dataset_id", "")
            if item.get("status") in ("parsing", "queued") and rf_doc_id and rf_dataset_id:
                rf_status = await ragflow_service.get_document_status(rf_dataset_id, rf_doc_id)
                new_status = ragflow_service.map_status(rf_status)
                # 只允许向前推进：parsed/failed 终态，或 queued→parsing 升级
                # 防止 parsing→queued 回退（RAGFlow 可能尚未更新状态）
                if new_status != item.get("status") and new_status != "queued":
                    await col.update_one({"_id": item["_id"]}, {"$set": {"status": new_status}})
                    item["status"] = new_status

    items = [_doc_response(doc).model_dump() for doc in items_raw]

    return ApiResponse(success=True, data={"items": items, "total": total, "page": page, "limit": limit})


# ════════════════════════════════════════════════════
# 单独同步文档状态（供前端轮询）
# ════════════════════════════════════════════════════

@router.post("/documents/{doc_id}/sync-status")
async def sync_document_status(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
):
    """手动触发单篇文档的 RAGFlow 状态同步"""
    col = get_collection("knowledge_documents")
    try:
        obj_id = ObjectId(doc_id)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的文档 ID")

    doc = await col.find_one({"_id": obj_id})
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    rf_doc_id = doc.get("ragflow_doc_id", "")
    rf_dataset_id = doc.get("ragflow_dataset_id", "")

    if not rf_doc_id or not rf_dataset_id:
        return ApiResponse(success=True, data={"status": doc.get("status", "ready")})

    rf_status = await ragflow_service.get_document_status(rf_dataset_id, rf_doc_id)
    new_status = ragflow_service.map_status(rf_status)
    # 防止 parsing→queued 回退（RAGFlow 尚未更新状态时）
    if new_status != doc.get("status") and new_status != "queued":
        await col.update_one({"_id": obj_id}, {"$set": {"status": new_status}})
        doc["status"] = new_status

    return ApiResponse(success=True, data={"status": doc.get("status", "ready")})


# ════════════════════════════════════════════════════
# 删除文档
# ════════════════════════════════════════════════════

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
):
    """删除知识库文档 — 同时从 RAGFlow 清理"""
    col = get_collection("knowledge_documents")
    try:
        obj_id = ObjectId(doc_id)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的文档 ID")

    doc = await col.find_one({"_id": obj_id})
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 从 RAGFlow 删除
    rf_doc_id = doc.get("ragflow_doc_id", "")
    rf_dataset_id = doc.get("ragflow_dataset_id", "")
    if rf_doc_id and rf_dataset_id:
        await ragflow_service.delete_document(rf_dataset_id, rf_doc_id)

    # 删除本地文件
    file_path = doc.get("file_path", "")
    if file_path and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError:
            logger.warning("Failed to delete file: %s", file_path)

    await col.delete_one({"_id": obj_id})
    return ApiResponse(success=True, message="文档已删除")


# ════════════════════════════════════════════════════
# 更新文档信息
# ════════════════════════════════════════════════════

@router.put("/documents/{doc_id}")
async def update_document(
    doc_id: str,
    body: KnowledgeDocUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新文档标题、描述、标签"""
    col = get_collection("knowledge_documents")
    try:
        obj_id = ObjectId(doc_id)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的文档 ID")

    update_data = {}
    if body.title is not None:
        update_data["title"] = body.title.strip()
    if body.description is not None:
        update_data["description"] = body.description.strip()
    if body.tags is not None:
        update_data["tags"] = body.tags

    if not update_data:
        raise HTTPException(status_code=400, detail="无更新字段")

    result = await col.update_one({"_id": obj_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="文档不存在")

    doc = await col.find_one({"_id": obj_id})
    return ApiResponse(success=True, data=_doc_response(doc).model_dump())


# ════════════════════════════════════════════════════
# 获取 RAGFlow 信息
# ════════════════════════════════════════════════════

@router.get("/ragflow/status")
async def ragflow_status(current_user: dict = Depends(get_current_user)):
    """获取 RAGFlow 连接状态及默认知识库信息"""
    try:
        dataset_id = await ragflow_service.resolve_default_dataset()
        datasets = await ragflow_service.list_datasets()
        dataset_info = None
        for ds in datasets:
            if ds.get("id") == dataset_id:
                dataset_info = ds
                break

        # 统计知识库中文档数
        docs = await ragflow_service.list_documents(dataset_id, page_size=1)
        total_docs = len(docs) if isinstance(docs, list) else 0

        return ApiResponse(success=True, data={
            "enabled": True,
            "dataset": {
                "id": dataset_id,
                "name": ragflow_service.RAGFLOW_DEFAULT_DATASET_NAME,
                "info": dataset_info,
                "document_count": total_docs,
                "chunk_count": dataset_info.get("chunk_count", 0) if dataset_info else 0,
            },
        })
    except Exception as e:
        return ApiResponse(success=True, data={
            "enabled": True,
            "error": str(e),
            "dataset": None,
        })


# ════════════════════════════════════════════════════
# 获取支持的格式
# ════════════════════════════════════════════════════

@router.get("/formats")
async def list_formats(current_user: dict = Depends(get_current_user)):
    return ApiResponse(success=True, data={"formats": sorted(ALLOWED_FORMATS)})

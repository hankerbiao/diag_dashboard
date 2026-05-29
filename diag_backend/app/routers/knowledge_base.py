"""Knowledge Base Router - Local storage + RAGFlow auto-sync"""
import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from ..core.auth import get_current_user
from ..core.config import get_settings
from ..core.mongodb import get_collection
from ..core.utils import utc_now_iso, parse_object_id
from ..models.request import KnowledgeBaseSearchRequest, KnowledgeDocUpdateRequest
from ..models.response import ApiResponse, KnowledgeDocResponse
from ..services import ragflow_service

ALLOWED_FORMATS = {"pdf", "docx", "md", "txt", "pptx", "xlsx", "csv", "html", "json", "xml"}
MAX_FILE_SIZE = 50 * 1024 * 1024
router = APIRouter(prefix="/knowledge-base", tags=["知识库"])


def _doc_response(doc: dict) -> KnowledgeDocResponse:
    return KnowledgeDocResponse(
        id=str(doc.get("_id")) if "_id" in doc else doc.get("id", ""),
        title=doc.get("title", ""), description=doc.get("description", ""),
        format=doc.get("format", ""), size_bytes=doc.get("size_bytes", 0),
        status=doc.get("status", "ready"), tags=doc.get("tags", []),
        uploaded_at=doc.get("uploaded_at"),
    )


def _build_doc(file: UploadFile, title: Optional[str], description: Optional[str],
               tags: Optional[str], user_id: str) -> dict:
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    storage_dir = os.path.join(get_settings().knowledge_base_storage_path, "")
    os.makedirs(storage_dir, exist_ok=True)
    return {
        "title": (title or "").strip() or file.filename.rsplit(".", 1)[0],
        "description": (description or "").strip(), "format": ext,
        "file_path": os.path.join(storage_dir, f"{uuid.uuid4().hex}.{ext}"),
        "file_id": uuid.uuid4().hex, "tags": [t.strip() for t in (tags or "").split(",") if t.strip()],
        "user_id": user_id, "uploaded_at": utc_now_iso(),
        "ragflow_dataset_id": "", "ragflow_doc_id": "", "status": "ready",
    }


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...), title: Optional[str] = Form(None),
    description: Optional[str] = Form(""), tags: Optional[str] = Form(""),
    current_user: dict = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    if ext not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: .{ext}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小超过限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)")

    doc = _build_doc(file, title, description, tags, current_user.get("user_id", ""))
    with open(doc["file_path"], "wb") as f:
        f.write(contents)
    doc["size_bytes"] = len(contents)

    col = get_collection("knowledge_documents")
    result = await col.insert_one(doc)
    doc["_id"] = result.inserted_id

    dataset_id = await ragflow_service.resolve_default_dataset()
    rf_resp = await ragflow_service.upload_document(dataset_id=dataset_id, file_path=doc["file_path"], file_name=file.filename)
    rf_doc_id = rf_resp.get("id", "")
    if rf_doc_id:
        await col.update_one({"_id": result.inserted_id},
                             {"$set": {"ragflow_dataset_id": dataset_id, "ragflow_doc_id": rf_doc_id, "status": "queued"}})
        await ragflow_service.run_parsing(dataset_id=dataset_id, document_ids=[rf_doc_id])
        doc["status"] = ragflow_service.map_status(await ragflow_service.get_document_status(dataset_id, rf_doc_id))
        await col.update_one({"_id": result.inserted_id}, {"$set": {"status": doc["status"]}})

    return ApiResponse(success=True, data=_doc_response(doc).model_dump())


@router.get("/documents")
async def list_documents(
    search: Optional[str] = Query(None), format: Optional[str] = Query(None),
    tag: Optional[str] = Query(None), sync_status: bool = Query(False),
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("knowledge_documents")
    query = {k: v for k, v in {
        "title": {"$regex": search, "$options": "i"} if search else None,
        "format": format, "tags": tag,
    }.items() if v}
    items = await col.find(query).sort("uploaded_at", -1).skip((page - 1) * limit).limit(limit).to_list(length=limit)

    if sync_status:
        for item in items:
            rf_doc_id, rf_dataset_id = item.get("ragflow_doc_id", ""), item.get("ragflow_dataset_id", "")
            if item.get("status") in ("parsing", "queued") and rf_doc_id and rf_dataset_id:
                new_status = ragflow_service.map_status(await ragflow_service.get_document_status(rf_dataset_id, rf_doc_id))
                if new_status != item.get("status") and new_status != "queued":
                    await col.update_one({"_id": item["_id"]}, {"$set": {"status": new_status}})
                    item["status"] = new_status

    total = await col.count_documents(query)
    return ApiResponse(success=True, data={"items": [_doc_response(doc).model_dump() for doc in items],
                          "total": total, "page": page, "limit": limit})


@router.post("/documents/{doc_id}/sync-status")
async def sync_document_status(doc_id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("knowledge_documents")
    doc = await col.find_one({"_id": parse_object_id(doc_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    rf_doc_id = doc.get("ragflow_doc_id", "")
    rf_dataset_id = doc.get("ragflow_dataset_id", "")
    if not (rf_doc_id and rf_dataset_id):
        return ApiResponse(success=True, data={"status": doc.get("status", "ready")})
    new_status = ragflow_service.map_status(await ragflow_service.get_document_status(rf_dataset_id, rf_doc_id))
    if new_status != doc.get("status") and new_status != "queued":
        await col.update_one({"_id": doc["_id"]}, {"$set": {"status": new_status}})
    return ApiResponse(success=True, data={"status": new_status if new_status != doc.get("status") and new_status != "queued" else doc.get("status", "ready")})


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("knowledge_documents")
    doc = await col.find_one({"_id": parse_object_id(doc_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if doc.get("ragflow_doc_id") and doc.get("ragflow_dataset_id"):
        await ragflow_service.delete_document(doc["ragflow_dataset_id"], doc["ragflow_doc_id"])
    file_path = doc.get("file_path", "")
    if file_path and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass
    await col.delete_one({"_id": doc["_id"]})
    return ApiResponse(success=True, message="文档已删除")


@router.put("/documents/{doc_id}")
async def update_document(doc_id: str, body: KnowledgeDocUpdateRequest, current_user: dict = Depends(get_current_user)):
    col = get_collection("knowledge_documents")
    update_data = {k: v.strip() if isinstance(v, str) else v
                   for k, v in {"title": body.title, "description": body.description, "tags": body.tags}.items()
                   if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="无更新字段")
    result = await col.update_one({"_id": parse_object_id(doc_id)}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="文档不存在")
    doc = await col.find_one({"_id": parse_object_id(doc_id)})
    return ApiResponse(success=True, data=_doc_response(doc).model_dump())


@router.get("/ragflow/status")
async def ragflow_status(current_user: dict = Depends(get_current_user)):
    try:
        dataset_id = await ragflow_service.resolve_default_dataset()
        datasets = await ragflow_service.list_datasets()
        dataset_info = next((ds for ds in datasets if ds.get("id") == dataset_id), None)
        docs = await ragflow_service.list_documents(dataset_id, page_size=1)
        return ApiResponse(success=True, data={
            "enabled": True, "dataset": {
                "id": dataset_id, "name": ragflow_service.RAGFLOW_DEFAULT_DATASET_NAME, "info": dataset_info,
                "document_count": len(docs) if isinstance(docs, list) else 0,
                "chunk_count": dataset_info.get("chunk_count", 0) if dataset_info else 0,
            },
        })
    except Exception as e:
        return ApiResponse(success=True, data={"enabled": True, "error": str(e), "dataset": None})


@router.post("/search")
async def search_knowledge_base(body: KnowledgeBaseSearchRequest, current_user: dict = Depends(get_current_user)):
    try:
        result = await ragflow_service.search_knowledge_base(
            question=body.question, similarity_threshold=0.2, vector_similarity_weight=0.3)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, error=f"知识库检索失败: {str(e)}")


@router.get("/formats")
async def list_formats(current_user: dict = Depends(get_current_user)):
    return ApiResponse(success=True, data={"formats": sorted(ALLOWED_FORMATS)})
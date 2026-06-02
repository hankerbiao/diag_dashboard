"""知识库相关响应模型"""
from pydantic import BaseModel
from typing import Optional


class KnowledgeDocResponse(BaseModel):
    id: str
    title: str
    description: str = ""
    format: str = ""
    size_bytes: int = 0
    status: str = "ready"
    tags: list[str] = []
    uploaded_at: Optional[str] = None

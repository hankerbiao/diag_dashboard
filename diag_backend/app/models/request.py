from pydantic import BaseModel
from typing import List, Optional


class DiagnosisBySNRequest(BaseModel):
    sn: str
    factory: str
    include_history: bool = True


class DiagnosisByErrorLogRequest(BaseModel):
    error_log_id: str


class SettingsUpdateRequest(BaseModel):
    ai_api_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    ai_temperature: Optional[float] = None
    active_kbs: Optional[list[str]] = None


class ReAnalyzeRequest(BaseModel):
    error_log_id: str


class KnowledgeDocUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class KnowledgeBaseSearchRequest(BaseModel):
    question: str
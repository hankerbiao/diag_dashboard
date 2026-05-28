from pydantic import BaseModel
from typing import List, Optional


class DiagnosisBySNRequest(BaseModel):
    sn: str
    factory: str
    include_history: bool = True


class DiagnosisByErrorLogRequest(BaseModel):
    error_log_id: str


class GlobalAiConfigUpdateRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    provider: Optional[str] = None


class ReAnalyzeRequest(BaseModel):
    error_log_id: str


class KnowledgeDocUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class KnowledgeBaseSearchRequest(BaseModel):
    question: str


class DiagnosisFollowUpRequest(BaseModel):
    sn: str
    question: str
    diagnosis_context: str


class SaveSnHistoryRequest(BaseModel):
    sn: str
    factory: str
    diagnosis_result: dict


class AppendChatRequest(BaseModel):
    role: str
    content: str


class FactoryOverride(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = None
    cutoff_hours: Optional[int] = None


class AutoSyncConfigUpdateRequest(BaseModel):
    sims_enabled: Optional[bool] = None
    sims_interval_minutes: Optional[int] = None
    factory_overrides: Optional[dict[str, FactoryOverride]] = None
    mes_enabled: Optional[bool] = None
    mes_interval_minutes: Optional[int] = None

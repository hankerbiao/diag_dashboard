from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional


class DiagnosisBySNRequest(BaseModel):
    sn: str = Field(..., min_length=1)
    factory: str = Field(..., min_length=1)
    include_history: bool = True

    @field_validator("sn", "factory")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


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
    sn: str = Field(..., min_length=1)
    factory: str = Field(..., min_length=1)
    diagnosis_result: dict

    @field_validator("sn", "factory")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class AppendChatRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


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

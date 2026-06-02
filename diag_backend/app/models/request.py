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


class ErrorLogAnalyzeContext(BaseModel):
    """测试详情行上下文（MES 实时数据），用于智能剖析时避免仅依赖合成 ID 回查。"""

    factory_id: str = ""
    server_sn: str = ""
    test_time: str = ""
    test_item: str = ""
    fail_details: str = ""
    log_path: str = ""
    fault_type1: str = ""
    fault_type2: str = ""
    fault_type3: str = ""

    @field_validator(
        "factory_id",
        "server_sn",
        "test_time",
        "test_item",
        "fail_details",
        "log_path",
        "fault_type1",
        "fault_type2",
        "fault_type3",
        mode="before",
    )
    @classmethod
    def strip_fields(cls, v):
        return v.strip() if isinstance(v, str) else v


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

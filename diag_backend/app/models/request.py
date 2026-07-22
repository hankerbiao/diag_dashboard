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
    max_tokens: Optional[int] = None
    chat_template_kwargs: Optional[dict] = None
    timeout: Optional[int] = None
    # 错误日志提取模型（快速）配置；留空则复用上方回答模型配置
    extraction_api_key: Optional[str] = None
    extraction_base_url: Optional[str] = None
    extraction_model: Optional[str] = None
    extraction_max_tokens: Optional[int] = None
    extraction_timeout: Optional[int] = None


class LogExtractionPromptRequest(BaseModel):
    """按机型配置的错误日志提取 prompt。model="default" 表示默认 prompt。"""
    model: str = Field(..., min_length=1)
    system_prompt: str = Field(..., min_length=1)
    user_template: str = Field(..., min_length=1)


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


class DiagnosisFeedbackRequest(BaseModel):
    """诊断反馈请求 - 用于收集用户对 AI 诊断结果的评价"""
    history_id: Optional[str] = None  # 诊断历史 ID（可选，若无则用 sn+factory 定位）
    sn: str = Field(..., min_length=1)
    factory: str = Field(..., min_length=1)
    rating: Literal["solved", "partially", "unsolved"] = Field(..., description="solved=可以解决, partially=解决一部分, unsolved=没有解决")
    comment: Optional[str] = Field(None, max_length=2000, description="用户反馈（解决一部分/没有解决时必填）")
    diagnosis_context: Optional[str] = Field(None, max_length=5000, description="诊断摘要上下文，便于后期分析")

    @field_validator("sn", "factory")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

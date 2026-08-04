from pydantic import BaseModel, Field, field_validator, model_validator
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


class AiModelConnectivityTestRequest(BaseModel):
    """使用未保存的表单配置测试 OpenAI 兼容模型服务。"""

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    timeout: Optional[int] = Field(None, ge=3, le=3600)
    extraction_api_key: Optional[str] = None
    extraction_base_url: Optional[str] = None
    extraction_model: Optional[str] = None
    extraction_timeout: Optional[int] = Field(None, ge=3, le=3600)


class LogExtractionPromptRequest(BaseModel):
    """按机型配置的错误日志提取 prompt。model="default" 表示默认 prompt。"""
    model: str = Field(..., min_length=1)
    system_prompt: str = Field(..., min_length=1)
    user_template: str = Field(..., min_length=1)


class RuntimeConfigUpdateRequest(BaseModel):
    """运行时性能配置更新（日志提取并发参数，保存后实时生效）。"""

    per_request_concurrency: Optional[int] = Field(
        None, ge=1, le=64, description="单请求内并发提取段数"
    )
    global_concurrency: Optional[int] = Field(
        None, ge=1, le=128, description="进程级全局并发提取上限"
    )

    @model_validator(mode="after")
    def _check_relation(self) -> "RuntimeConfigUpdateRequest":
        per = self.per_request_concurrency
        glo = self.global_concurrency
        if per is not None and glo is not None and glo < per:
            raise ValueError("全局并发上限不能小于单请求并发")
        return self


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


class DiagnosisFeedbackStatusRequest(BaseModel):
    """反馈处理状态更新请求。"""

    status: Literal["pending", "processing", "resolved", "ignored"]
    resolution_note: Optional[str] = Field(None, max_length=2000)


class DiagnosisFeedbackKnowledgeRequest(BaseModel):
    """反馈补充到知识库后的文档关联信息。"""

    document_ids: list[str] = Field(..., min_length=1, max_length=20)
    knowledge_title: str = Field(..., min_length=1, max_length=200)

    @field_validator("document_ids")
    @classmethod
    def normalize_document_ids(cls, values: list[str]) -> list[str]:
        document_ids = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not document_ids:
            raise ValueError("document_ids 至少包含一个有效文档 ID")
        return document_ids

    @field_validator("knowledge_title")
    @classmethod
    def normalize_knowledge_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("knowledge_title 不能为空")
        return title

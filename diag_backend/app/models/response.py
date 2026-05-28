from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class ErrorLogResponse(BaseModel):
    id: str
    sn: str
    test_item: str
    test_time: datetime
    status: str
    user_choice: Optional[str]
    mes_reported: bool
    fail_details: Optional[str]


class ReferenceLog(BaseModel):
    id: str
    source: str
    timestamp: str
    content: str


class MaintenanceRecord(BaseModel):
    id: str
    date: str
    component: str
    action: str


class TestLogItem(BaseModel):
    id: str
    test_item: str
    test_time: str
    fail_details: str
    fault_type1: str = ""
    fault_type2: str = ""
    fault_type3: str = ""
    decision: str = ""
    big_flow: str = ""
    log_path: str = ""


class SimilarCaseItem(BaseModel):
    id: str
    title: str
    root_cause: str
    similarity: float = 0.0


class DiagnosisResponse(BaseModel):
    sn: str
    category: str
    summary: str
    confidence: float
    root_cause_detail: str = ""
    affected_components: list[str] = []
    suggestions: list[str]
    preventive_measures: list[str] = []
    reference_logs: list[ReferenceLog]
    maintenance_history: list[MaintenanceRecord]
    test_logs: list[TestLogItem] = []
    similar_cases: list[SimilarCaseItem] = []


class ErrorAnalysisResponse(BaseModel):
    error_log: ErrorLogResponse
    analysis: str
    root_cause: str
    repair_suggestions: list[str]
    similar_cases: list[dict]


class TrendDataPoint(BaseModel):
    time: str
    issues: int


class YieldDataPoint(BaseModel):
    date: str
    yield_: float = 0


class StatsByType(BaseModel):
    name: str
    count: int


class LineIssuesData(BaseModel):
    line: str
    issues: int


class ErrorLogsStatsResponse(BaseModel):
    trend: list[TrendDataPoint]
    yield_trend: list[YieldDataPoint]
    by_type: list[StatsByType]
    by_line: list[LineIssuesData]


class GlobalAiConfigResponse(BaseModel):
    api_key: str
    base_url: str
    model: str
    temperature: float
    provider: str
    updated_at: str
    updated_by: str


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None


class KnowledgeDocResponse(BaseModel):
    id: str
    title: str
    description: str = ""
    format: str = ""
    size_bytes: int = 0
    status: str = "ready"
    tags: list[str] = []
    uploaded_at: Optional[str] = None


class DiagnosisCacheResponse(BaseModel):
    id: str
    error_log_id: str
    sn: str
    test_item: str
    root_cause: str
    evidence: list[dict] = []
    analysis: str
    repair_suggestions: list[str]
    knowledge_refs: list[dict] = []
    log_content: str = ""
    created_at: str
    is_cached: bool = False


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    limit: int



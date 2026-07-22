"""诊断相关响应模型"""
from pydantic import BaseModel
from typing import Optional
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


class FailedLogFile(BaseModel):
    """被 AI 分析引用的失败日志文件信息（含提取内容，供前端下载）"""
    test_item: str
    test_time: str
    log_path: str
    extracted_content: str          # 智能提取后的日志内容
    matched_lines: int = 0          # 匹配到的错误行数
    total_lines: int = 0            # 日志总行数


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
    failed_test_logs: list[TestLogItem] = []
    failed_log_files: list[FailedLogFile] = []
    merged_error_log: str = ""
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


class DiagnosisCacheResponse(BaseModel):
    id: str
    error_log_id: str
    sn: str
    test_item: str
    root_cause: str
    evidence: list = []
    analysis: str
    repair_suggestions: list[str]
    knowledge_refs: list[dict] = []
    log_content: str = ""
    created_at: str
    is_cached: bool = False


class SnHistoryItem(BaseModel):
    id: str
    sn: str
    factory: str
    category: str
    confidence: float
    summary: str
    created_at: str


class SnHistoryDetail(BaseModel):
    id: str
    sn: str
    factory: str
    diagnosis_result: dict
    chat_messages: list[dict] = []
    created_at: str
    updated_at: str
    feedback_rating: Optional[str] = None
    feedback_comment: Optional[str] = None

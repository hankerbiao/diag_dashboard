from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DiagnosisBySNRequest(BaseModel):
    sn: str
    factory: str
    include_history: bool = True


class DiagnosisByErrorLogRequest(BaseModel):
    error_log_id: str


class ErrorLogQueryRequest(BaseModel):
    factory: str
    order_no: Optional[str] = None
    model_name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    ai_api_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    ai_temperature: Optional[float] = None
    active_kbs: Optional[list[str]] = None
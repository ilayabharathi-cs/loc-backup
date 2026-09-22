from typing import List, Optional
from pydantic import BaseModel
from app.schemas.activity import AuditLogResponse
from app.schemas.job import JobResponse

class DashboardSummaryResponse(BaseModel):
    total_clients: int
    online_clients: int
    offline_clients: int
    pending_clients: int
    successful_backups: int
    failed_backups: int
    running_backups: int
    storage_total: float
    storage_used: float
    storage_available: float
    average_rpo_seconds: int
    failed_jobs_last_24h: int
    recent_jobs: List[JobResponse] = []
    recent_activity: List[AuditLogResponse] = []

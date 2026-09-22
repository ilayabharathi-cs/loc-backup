import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class JobCreate(BaseModel):
    client_id: str  # Can be client_id string (e.g. PC-001) or integer id
    policy_id: Optional[int] = None

class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    client_id: int
    client_identifier: Optional[str] = None
    client_hostname: Optional[str] = None
    policy_id: Optional[int] = None
    policy_name: Optional[str] = None
    status: str
    scheduled_at: Optional[datetime.datetime] = None
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    data_processed_mb: Optional[float] = 0.0
    progress_percent: Optional[int] = 0

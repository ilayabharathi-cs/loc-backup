import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class RestoreJobCreate(BaseModel):
    source_client_id: str
    target_client_id: Optional[str] = None
    recovery_point_id: int
    source_path: str = Field(..., min_length=1)
    target_path: str = Field(..., min_length=1)
    acknowledge_cross_client: bool = False

class RestoreJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restore_id: str
    source_client_id: int
    source_client_identifier: Optional[str] = None
    target_client_id: int
    target_client_identifier: Optional[str] = None
    recovery_point_id: int
    source_path: str
    target_path: str
    status: str
    requested_by: str
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime

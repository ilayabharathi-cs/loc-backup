import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class StorageRepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    repository_type: str
    path: str
    total_bytes: int
    used_bytes: int
    available_bytes: int
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    total_tb: float = 0.0
    used_tb: float = 0.0
    free_tb: float = 0.0
    dedup_ratio: float = 2.8
    compression_ratio: float = 1.7
    disk_health: str = "OPTIMAL (S.M.A.R.T. Verified)"

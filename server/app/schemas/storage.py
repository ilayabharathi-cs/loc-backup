import datetime
from typing import Any, Dict, List, Optional
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


class StorageObjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: str
    content_sha256: str
    stored_sha256: str
    original_size: int
    stored_size: int
    compression_algorithm: str
    compression_ratio: float
    reference_count: int
    state: str
    integrity_status: str
    verified_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime


class StorageMetricsResponse(BaseModel):
    total_logical_bytes: int
    total_stored_bytes: int
    unique_original_bytes: int
    bytes_saved: int
    savings_percent: float
    deduplication_ratio: float
    compression_ratio: float
    overall_efficiency_ratio: float
    total_files_referenced: int
    unique_storage_objects: int
    repository_health: Dict[str, Any]


class StorageScrubRequest(BaseModel):
    batch_size: int = 100
    verify_content: bool = True
    object_id: Optional[str] = None


class StorageScrubResponse(BaseModel):
    objects_checked: int
    objects_valid: int
    objects_corrupted: int
    corrupted_items: List[Dict[str, Any]]
    timestamp: str


class GarbageCollectionTriggerRequest(BaseModel):
    dry_run: bool = False


class GarbageCollectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    candidates_found: int
    objects_deleted: int
    objects_skipped: int
    bytes_reclaimed: int
    error_message: Optional[str] = None

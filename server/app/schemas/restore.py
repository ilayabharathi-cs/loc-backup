import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class VirtualFileEntry(BaseModel):
    id: Optional[int] = None
    name: str
    path: str
    type: str  # file or directory
    size: int = 0
    sha256: Optional[str] = None
    change_type: Optional[str] = None
    modified_time: Optional[str] = None
    children: Optional[List["VirtualFileEntry"]] = None


class RestorePreviewRequest(BaseModel):
    recovery_point_id: int
    restore_mode: str = "FULL_RECOVERY_POINT"
    destination_root: str = Field(..., min_length=1)
    conflict_mode: str = "OVERWRITE"
    selected_paths: Optional[List[str]] = None


class RestorePreviewResponse(BaseModel):
    recovery_point_id: int
    source_client_id: str
    destination_root: str
    restore_mode: str
    conflict_mode: str
    total_files: int
    logical_bytes: int
    estimated_stored_read_bytes: int
    actions: Dict[str, int]
    items: List[Dict[str, Any]]


class RestoreJobCreate(BaseModel):
    source_client_id: str
    target_client_id: Optional[str] = None
    recovery_point_id: int
    source_path: str = Field(..., min_length=1)
    target_path: str = Field(..., min_length=1)
    restore_mode: str = "FULL_RECOVERY_POINT"  # FILE, FOLDER, SELECTION, FULL_RECOVERY_POINT
    conflict_mode: str = "OVERWRITE"          # SKIP, OVERWRITE, RENAME, FAIL
    metadata_mode: str = "BASIC"              # NONE, BASIC, FULL
    selected_paths: Optional[List[str]] = None
    acknowledge_cross_client: bool = False


class RestoreItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restore_job_id: int
    backup_file_id: Optional[int] = None
    relative_path: str
    destination_path: str
    source_size: int
    restored_size: int
    source_sha256: Optional[str] = None
    restored_sha256: Optional[str] = None
    status: str
    retry_count: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    verified_at: Optional[datetime.datetime] = None


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

    restore_mode: str = "FULL_RECOVERY_POINT"
    conflict_mode: str = "OVERWRITE"
    metadata_mode: str = "BASIC"

    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    skipped_files: int = 0

    total_bytes: int = 0
    restored_bytes: int = 0
    verified_bytes: int = 0
    progress_percent: float = 0.0

    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    cancelled_at: Optional[datetime.datetime] = None
    restore_requested_at: Optional[datetime.datetime] = None
    first_byte_restored_at: Optional[datetime.datetime] = None
    error_message: Optional[str] = None

    rto_metrics: Optional[Dict[str, Any]] = None
    created_at: datetime.datetime

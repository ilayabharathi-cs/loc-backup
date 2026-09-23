import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class BackupRunCreate(BaseModel):
    client_id: str  # PC-001 or integer id
    policy_id: Optional[int] = None
    backup_type: str = "full"
    files_discovered: int = 0
    bytes_total: int = 0
    baseline_run_id: Optional[int] = None
    prevent_concurrent: bool = False


class BackupRunProgressUpdate(BaseModel):
    files_discovered: Optional[int] = None
    files_uploaded: Optional[int] = None
    files_failed: Optional[int] = None
    files_new: Optional[int] = None
    files_modified: Optional[int] = None
    files_unchanged: Optional[int] = None
    files_deleted: Optional[int] = None
    bytes_total: Optional[int] = None
    bytes_uploaded: Optional[int] = None
    current_file: Optional[str] = None
    error_count: Optional[int] = None
    error_message: Optional[str] = None


class BackupRunCompleteRequest(BaseModel):
    status: str = "completed"  # completed, failed, completed_with_warnings
    files_uploaded: int
    files_failed: int = 0
    bytes_uploaded: int
    files_discovered: Optional[int] = None
    bytes_total: Optional[int] = None
    files_new: int = 0
    files_modified: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    error_count: int = 0
    error_message: Optional[str] = None


class BackupRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    client_id: int
    client_identifier: Optional[str] = None
    policy_id: Optional[int] = None
    backup_type: str
    baseline_run_id: Optional[int] = None
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    status: str
    state: str = "CREATED"
    lease_id: Optional[str] = None
    lease_expires_at: Optional[datetime.datetime] = None
    interrupted_at: Optional[datetime.datetime] = None
    resumed_at: Optional[datetime.datetime] = None
    checkpoint_version: int = 1
    retry_count: int = 0
    files_locked: int = 0
    files_vss_recovered: int = 0
    files_skipped: int = 0
    files_processed: int
    files_discovered: int = 0
    files_uploaded: int = 0
    files_failed: int = 0
    files_new: int = 0
    files_modified: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    bytes_total: int = 0
    bytes_processed: int
    bytes_uploaded: int
    error_count: int
    error_message: Optional[str] = None


class UploadSessionCreateRequest(BaseModel):
    file_path: str
    relative_path: Optional[str] = None
    total_size: int
    chunk_size: int = 4194304
    change_type: str = "FULL"
    file_mtime: Optional[datetime.datetime] = None
    expected_sha256: Optional[str] = None


class UploadSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    upload_session_id: str
    run_id: int
    object_id: str
    chunk_size: int
    total_chunks: int
    next_chunk_index: int
    received_bytes: int
    status: str


class UploadSessionStatusResponse(BaseModel):
    upload_session_id: str
    status: str
    total_chunks: int
    received_bytes: int
    total_size: int
    next_chunk_index: int
    received_chunks: List[int]


class ChunkUploadResponse(BaseModel):
    upload_session_id: str
    chunk_index: int
    offset: int
    size: int
    sha256: str
    status: str
    already_existed: bool = False


class UploadSessionCompleteRequest(BaseModel):
    final_sha256: str
    total_size: int


class RunStateUpdateRequest(BaseModel):
    state: str
    message: Optional[str] = None


class RunStateResponse(BaseModel):
    run_id: int
    state: str
    status: str
    lease_id: Optional[str] = None
    lease_expires_at: Optional[datetime.datetime] = None
    interrupted_at: Optional[datetime.datetime] = None
    resumed_at: Optional[datetime.datetime] = None


class RunCheckpointRequest(BaseModel):
    current_file: Optional[str] = None
    bytes_uploaded: int = 0
    last_chunk_index: int = 0
    state: str = "BACKING_UP"
    checkpoint_version: int = 1


class RunCheckpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    checkpoint_id: int
    run_id: int
    client_id: int
    state: str
    current_file: Optional[str] = None
    bytes_uploaded: int = 0
    last_chunk_index: int = 0
    checkpoint_version: int = 1
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RunLeaseRenewRequest(BaseModel):
    lease_id: str
    duration_seconds: int = 300


class RunLeaseRenewResponse(BaseModel):
    lease_id: str
    lease_expires_at: datetime.datetime
    is_valid: bool


class RunEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    event_type: str
    message: str
    timestamp: datetime.datetime
    event_metadata: Optional[str] = None



class RecoveryPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    client_identifier: Optional[str] = None
    client_hostname: Optional[str] = None
    backup_run_id: int
    backup_type: Optional[str] = "full"
    timestamp: datetime.datetime
    files_count: int
    total_size_bytes: int
    status: str
    created_at: datetime.datetime
    retention_status: Optional[str] = "active"
    is_daily: Optional[bool] = False
    is_weekly: Optional[bool] = False
    is_monthly: Optional[bool] = False
    is_yearly: Optional[bool] = False
    is_manual_protected: Optional[bool] = False
    expires_at: Optional[datetime.datetime] = None
    retention_tier: Optional[str] = None


class BackupFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    original_path: str
    relative_path: Optional[str] = None
    file_name: str
    size_bytes: int
    sha256: Optional[str] = None
    version: int
    backup_run_id: int
    storage_object: Optional[str] = None
    storage_object_id: Optional[int] = None
    upload_status: str = "completed"
    change_type: Optional[str] = "FULL"
    modified_time: Optional[datetime.datetime] = None
    created_at: datetime.datetime


class FileMetadataRecord(BaseModel):
    original_path: str
    relative_path: Optional[str] = None
    file_name: str
    size_bytes: int = 0
    sha256: Optional[str] = None
    storage_object: Optional[str] = None
    change_type: str = "UNCHANGED"  # FULL, NEW, MODIFIED, UNCHANGED, DELETED
    upload_status: str = "completed"  # completed, deleted, failed
    modified_time: Optional[datetime.datetime] = None


class BatchFileMetadataRequest(BaseModel):
    files: List[FileMetadataRecord]


class ManifestFileEntry(BaseModel):
    id: int
    file_name: str
    original_path: str
    relative_path: Optional[str] = None
    size_bytes: int
    sha256: Optional[str] = None
    storage_object: Optional[str] = None
    change_type: str
    upload_status: str
    modified_time: Optional[datetime.datetime] = None
    created_at: datetime.datetime


class RecoveryPointManifestResponse(BaseModel):
    recovery_point_id: int
    backup_run_id: int
    client_id: int
    backup_type: str
    total_files: int
    total_size_bytes: int
    timestamp: datetime.datetime
    files: List[ManifestFileEntry]

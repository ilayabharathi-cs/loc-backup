import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class BackupRunCreate(BaseModel):
    client_id: str  # PC-001 or integer id
    policy_id: Optional[int] = None
    backup_type: str = "full"
    files_discovered: int = 0
    bytes_total: int = 0

class BackupRunProgressUpdate(BaseModel):
    files_discovered: Optional[int] = None
    files_uploaded: Optional[int] = None
    files_failed: Optional[int] = None
    bytes_total: Optional[int] = None
    bytes_uploaded: Optional[int] = None
    current_file: Optional[str] = None
    error_count: Optional[int] = None
    error_message: Optional[str] = None

class BackupRunCompleteRequest(BaseModel):
    status: str = "completed"  # completed, failed
    files_uploaded: int
    files_failed: int = 0
    bytes_uploaded: int
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
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    status: str
    files_processed: int
    files_discovered: int = 0
    files_uploaded: int = 0
    files_failed: int = 0
    bytes_total: int = 0
    bytes_processed: int
    bytes_uploaded: int
    error_count: int
    error_message: Optional[str] = None

class RecoveryPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    client_identifier: Optional[str] = None
    client_hostname: Optional[str] = None
    backup_run_id: int
    timestamp: datetime.datetime
    files_count: int
    total_size_bytes: int
    status: str
    created_at: datetime.datetime

class BackupFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    original_path: str
    relative_path: Optional[str] = None
    file_name: str
    size_bytes: int
    sha256: str
    version: int
    backup_run_id: int
    storage_object: Optional[str] = None
    upload_status: str = "completed"
    modified_time: Optional[datetime.datetime] = None
    created_at: datetime.datetime

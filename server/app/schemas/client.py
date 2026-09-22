import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class ClientBase(BaseModel):
    hostname: str
    os: str
    os_version: Optional[str] = None
    ip_address: str
    agent_version: str

class ClientCreate(ClientBase):
    client_id: str
    device_id: str
    status: str = "pending"

class ClientUpdate(BaseModel):
    hostname: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    ip_address: Optional[str] = None
    agent_version: Optional[str] = None
    status: Optional[str] = None

class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: str
    device_id: str
    status: str
    last_seen: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

class AgentRegisterRequest(BaseModel):
    hostname: str
    device_id: str
    os: str
    os_version: Optional[str] = None
    ip_address: str
    agent_version: str

class AgentHeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    device_id: str
    client_id: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    agent_version: Optional[str] = None
    status: Optional[str] = "active"
    timestamp: Optional[datetime.datetime] = None
    cpu_usage_percent: Optional[float] = None
    memory_usage_percent: Optional[float] = None
    available_disk_space_bytes: Optional[int] = None
    total_disk_space_bytes: Optional[int] = None
    backup_state: Optional[str] = None
    last_successful_backup: Optional[datetime.datetime] = None
    errors: Optional[List[str]] = None

class AgentConfigResponse(BaseModel):
    client_id: str
    device_id: str
    status: str
    server_time: datetime.datetime
    heartbeat_interval_seconds: int = 15
    policy: Optional[dict] = None
    pending_job: Optional[dict] = None

"""RetroVault V11: Workload Provider Framework & Abstractions."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import datetime


# Consistency states
FILE_SYSTEM_CONSISTENT = "FILE_SYSTEM_CONSISTENT"
APPLICATION_CONSISTENT = "APPLICATION_CONSISTENT"
CRASH_CONSISTENT = "CRASH_CONSISTENT"
PARTIAL = "PARTIAL"
UNKNOWN = "UNKNOWN"
FAILED = "FAILED"

# Workload status
STATUS_DISCOVERED = "DISCOVERED"
STATUS_PREPARING = "PREPARING"
STATUS_QUIESCING = "QUIESCING"
STATUS_BACKING_UP = "BACKING_UP"
STATUS_VERIFYING = "VERIFYING"
STATUS_COMPLETING = "COMPLETING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_PARTIAL = "PARTIAL"
STATUS_CANCELLED = "CANCELLED"

# Capability states
CAPABILITY_SUPPORTED = "SUPPORTED"
CAPABILITY_UNSUPPORTED = "UNSUPPORTED"
CAPABILITY_DEGRADED = "DEGRADED"
CAPABILITY_FAILED = "FAILED"


@dataclass
class HookResult:
    success: bool
    phase: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    error: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuiesceResult:
    success: bool
    quiesced_at: Optional[datetime.datetime] = None
    unquiesced_at: Optional[datetime.datetime] = None
    freeze_duration_ms: float = 0.0
    lsn: Optional[str] = None
    checkpoint_id: Optional[str] = None
    error: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupArtifactResult:
    success: bool
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    total_bytes: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsistencyResult:
    consistency_state: str  # APPLICATION_CONSISTENT, CRASH_CONSISTENT, etc.
    verification_method: str
    verified: bool
    evidence: Dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None


@dataclass
class RestorePreviewResult:
    workload_id: str
    source_recovery_point_id: str
    target_destination: str
    estimated_size_bytes: int
    overwrite_conflicts: List[str] = field(default_factory=list)
    required_dependencies: List[str] = field(default_factory=list)
    consistency_status: str = UNKNOWN
    validation_plan: List[str] = field(default_factory=list)
    is_safe_to_proceed: bool = True
    blockers: List[str] = field(default_factory=list)


@dataclass
class RestoreExecutionResult:
    success: bool
    current_phase: str
    phases_completed: List[str] = field(default_factory=list)
    restored_bytes: int = 0
    artifacts_restored: int = 0
    verification_passed: bool = False
    validation_passed: bool = False
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class WorkloadProvider(ABC):
    """Abstract base provider for application-aware data protection."""

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Provider identifier, e.g. WINDOWS_FILESYSTEM, MSSQL, POSTGRESQL, GENERIC_APP."""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities (quiesce, PITR, log_backup, etc.)."""
        pass

    @abstractmethod
    def discover(self, client_id: str, config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Discover instances or components of this workload on the given client."""
        pass

    @abstractmethod
    def pre_snapshot_hook(self, context: Dict[str, Any]) -> HookResult:
        """Execute pre-snapshot validation or preparation."""
        pass

    @abstractmethod
    def quiesce(self, context: Dict[str, Any]) -> QuiesceResult:
        """Quiesce the application to achieve an application-consistent state."""
        pass

    @abstractmethod
    def snapshot_backup(self, context: Dict[str, Any]) -> BackupArtifactResult:
        """Perform the actual application or database backup snapshot."""
        pass

    @abstractmethod
    def unquiesce(self, context: Dict[str, Any]) -> HookResult:
        """Thaw/unquiesce the application after snapshot."""
        pass

    @abstractmethod
    def post_snapshot_hook(self, context: Dict[str, Any]) -> HookResult:
        """Execute post-snapshot cleanup, log truncation, or validation."""
        pass

    @abstractmethod
    def verify_consistency(self, context: Dict[str, Any]) -> ConsistencyResult:
        """Rigorously verify consistency using provider-specific signals."""
        pass

    @abstractmethod
    def restore_preview(self, context: Dict[str, Any]) -> RestorePreviewResult:
        """Preview application restore, detecting conflicts, size, and dependencies."""
        pass

    @abstractmethod
    def restore_workload(self, context: Dict[str, Any]) -> RestoreExecutionResult:
        """Execute workload restore through discovery -> precheck -> prepare -> restore -> verify -> validate -> complete."""
        pass

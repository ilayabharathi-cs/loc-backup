"""RetroVault V8 Enterprise Security, Ransomware Resilience & Fleet Models."""

import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Integer, BigInteger, Float, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    # Types: RANSOMWARE_SUSPECTED, MASS_MODIFICATION, EXTENSION_TRANSFORMATION, HIGH_ENTROPY,
    #        UNUSUAL_DELETION, REPOSITORY_TAMPER, INTEGRITY_FAILURE, AGENT_TAMPER, CONFIG_DRIFT
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM", index=True, nullable=False)
    # Severities: LOW, MEDIUM, HIGH, CRITICAL

    client_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    repository_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("storage_repositories.id", ondelete="SET NULL"), nullable=True, index=True)
    run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("backup_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    recovery_point_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("recovery_points.id", ondelete="SET NULL"), nullable=True, index=True)

    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 to 100
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True, nullable=False)
    # Statuses: OPEN, ACKNOWLEDGED, INVESTIGATING, MITIGATED, RESOLVED, FALSE_POSITIVE

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    acknowledged_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    client = relationship("Client")
    repository = relationship("StorageRepository")
    run = relationship("BackupRun")
    recovery_point = relationship("RecoveryPoint")


class SecurityIncident(Base):
    __tablename__ = "security_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    incident_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="HIGH", index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="DETECTED", index=True, nullable=False)
    # Lifecycle: DETECTED, TRIAGED, CONTAINED, RECOVERY_CANDIDATE_SELECTED,
    #            RESTORE_TESTED, RECOVERY_APPROVED, RECOVERY_EXECUTED, VERIFIED, CLOSED

    client_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    candidate_recovery_point_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("recovery_points.id", ondelete="SET NULL"), nullable=True)
    restore_test_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    containment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    closed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    client = relationship("Client")
    candidate_recovery_point = relationship("RecoveryPoint")


class SecurityProfile(Base):
    __tablename__ = "security_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    anomaly_threshold: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    max_deletion_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_deletion_pct: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    require_mfa_for_deletion: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    entropy_threshold: Mapped[float] = mapped_column(Float, default=7.2, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    groups = relationship("ClientGroup", back_populates="security_profile")


class ClientGroup(Base):
    __tablename__ = "client_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    policy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("backup_policies.id", ondelete="SET NULL"), nullable=True)
    security_profile_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("security_profiles.id", ondelete="SET NULL"), nullable=True)
    repository_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("storage_repositories.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    policy = relationship("BackupPolicy")
    security_profile = relationship("SecurityProfile", back_populates="groups")
    repository = relationship("StorageRepository")
    clients = relationship("Client", back_populates="group")


class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("backup_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_json: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    policy = relationship("BackupPolicy")


class ConfigurationDrift(Base):
    __tablename__ = "configuration_drifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    drift_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: POLICY_MISMATCH, VERSION_MISMATCH, SCHEDULE_MISMATCH, PROFILE_MISMATCH
    expected_value: Mapped[str] = mapped_column(String(255), nullable=False)
    actual_value: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="WARNING", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DETECTED", nullable=False)
    # Statuses: DETECTED, RESOLVED, IGNORED

    detected_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    client = relationship("Client")


class IntegrityScan(Base):
    __tablename__ = "integrity_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scan_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    repository_id: Mapped[int] = mapped_column(Integer, ForeignKey("storage_repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_type: Mapped[str] = mapped_column(String(30), default="FULL", nullable=False)  # QUICK, FULL, CAS_OBJECTS
    total_objects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_objects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    corrupted_objects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_objects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="RUNNING", nullable=False)  # RUNNING, COMPLETED, FAILED
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    repository = relationship("StorageRepository")


class DeletionGuard(Base):
    __tablename__ = "deletion_guards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: DELETE_RECOVERY_POINT, BATCH_DELETE_RECOVERY_POINTS, DELETE_REPOSITORY
    requester_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requester_username: Mapped[str] = mapped_column(String(100), nullable=False)
    target_resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED, EXPIRED, EXECUTED
    risk_score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SecuritySimulation(Base):
    __tablename__ = "security_simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    simulation_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # Scenarios: MASS_MODIFICATION, EXTENSION_TRANSFORMATION, MASS_DELETION,
    #            REPOSITORY_CORRUPTION, CREDENTIAL_COMPROMISE, REPLICATION_OUTAGE
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)  # PENDING, RUNNING, PASSED, FAILED
    sandbox_path: Mapped[str] = mapped_column(String(500), nullable=False)
    parameters_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    results_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

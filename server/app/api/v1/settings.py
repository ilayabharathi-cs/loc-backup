"""Centralized Settings API router for RetroVault V7."""

import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.security_models import SystemSetting
from app.schemas.common import ApiResponse
from app.schemas.v7_schemas import SystemSettingUpdate, SystemSettingResponse
from app.security.dependencies import require_role, get_optional_current_user
from app.services.scheduler.operational_scheduler import OperationalScheduler
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/settings", tags=["Centralized Settings"])


DEFAULT_SETTINGS = [
    ("general", "general.company_name", "RetroVault Enterprise", "Enterprise organization name"),
    ("retention", "retention.default_days", "30", "Default recovery point retention in days"),
    ("retention", "retention.gfs_enabled", "true", "Enable Grandfather-Father-Son rotation"),
    ("replication", "replication.max_bandwidth_mbps", "100", "Global replication bandwidth cap"),
    ("security", "security.mfa_enforced", "false", "Enforce MFA for all administrators"),
    ("security", "security.token_ttl_hours", "720", "Agent authentication token expiration"),
    ("storage", "storage.low_disk_warning_pct", "85", "Threshold percentage for low disk warning"),
    ("alerts", "alerts.cooldown_minutes", "60", "Alert notification cooldown window"),
    ("dr", "dr.test_frequency_days", "30", "Automated DR test schedule frequency"),
    ("scheduler", "scheduler.heartbeat_timeout_seconds", "300", "Threshold for agent offline detection"),
    ("compliance", "compliance.immutability_period_days", "365", "Minimum protection retention")
]


def ensure_default_settings(db: Session):
    count = db.query(SystemSetting).count()
    if count == 0:
        for cat, k, v, desc in DEFAULT_SETTINGS:
            s = SystemSetting(category=cat, key=k, value=v, description=desc)
            db.add(s)
        db.commit()


@router.get("", response_model=ApiResponse[Dict[str, List[SystemSettingResponse]]])
def get_all_settings(db: Session = Depends(get_db)):
    """Retrieve all centralized system settings grouped by category."""
    ensure_default_settings(db)
    settings = db.query(SystemSetting).order_by(SystemSetting.category.asc(), SystemSetting.key.asc()).all()
    grouped: Dict[str, List[SystemSettingResponse]] = {}
    for s in settings:
        if s.category not in grouped:
            grouped[s.category] = []
        grouped[s.category].append(SystemSettingResponse.model_validate(s))
    return ApiResponse(success=True, data=grouped, message="Retrieved centralized system settings")


@router.put("/{key}", response_model=ApiResponse[SystemSettingResponse])
def update_setting(
    key: str,
    request: SystemSettingUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"]))
):
    """Update a centralized configuration setting."""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        cat = key.split(".")[0] if "." in key else "general"
        setting = SystemSetting(category=cat, key=key, value=request.value, description=request.description or key)
        db.add(setting)
        db.commit()
        db.refresh(setting)

    old_val = setting.value
    setting.value = request.value
    if request.description:
        setting.description = request.description
    setting.updated_at = datetime.datetime.now(datetime.timezone.utc)
    setting.updated_by = current_user.username if current_user else "Administrator"

    db.commit()
    db.refresh(setting)

    log_audit_event(
        db=db,
        action="SETTING_UPDATED",
        resource_type="setting",
        resource_id=key,
        user_id=current_user.id if current_user else None,
        details=f"Updated setting {key}: '{old_val}' -> '{setting.value}'"
    )

    return ApiResponse(success=True, data=SystemSettingResponse.model_validate(setting), message=f"Setting '{key}' updated")


@router.get("/schedules", response_model=ApiResponse[List[Dict[str, Any]]])
def get_operational_schedules(db: Session = Depends(get_db)):
    """Retrieve active enterprise operational schedules and lock states."""
    scheduler = OperationalScheduler(db)
    schedules = scheduler.get_registered_schedules()
    return ApiResponse(success=True, data=schedules, message="Operational schedules retrieved")

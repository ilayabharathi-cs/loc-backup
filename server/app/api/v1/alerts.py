"""Alerts API router for RetroVault V7."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.alert import AlertRule, Alert
from app.schemas.common import ApiResponse
from app.schemas.v7_schemas import AlertRuleCreate, AlertRuleResponse, AlertResponse
from app.security.dependencies import require_role, get_optional_current_user
from app.services.alerts.alert_engine import AlertEngine

router = APIRouter(prefix="/alerts", tags=["Alerting & Notifications"])


@router.get("", response_model=ApiResponse[List[AlertResponse]])
def list_alerts(
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE, ACKNOWLEDGED, RESOLVED"),
    severity: Optional[str] = Query(None, description="Filter by severity: INFO, WARNING, ERROR, CRITICAL"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieve system alerts with optional status and severity filtering."""
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status.upper())
    if severity:
        query = query.filter(Alert.severity == severity.upper())

    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()
    return ApiResponse(
        success=True,
        data=[AlertResponse.model_validate(a) for a in alerts],
        message=f"Retrieved {len(alerts)} alerts"
    )


@router.post("/evaluate", response_model=ApiResponse[List[AlertResponse]])
def evaluate_alert_rules(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """Trigger evaluation of all active alert rules."""
    engine = AlertEngine(db)
    generated = engine.evaluate_rules()
    return ApiResponse(
        success=True,
        data=[AlertResponse.model_validate(a) for a in generated],
        message=f"Evaluated alert rules. Generated/updated {len(generated)} alerts."
    )


@router.post("/{alert_id}/acknowledge", response_model=ApiResponse[AlertResponse])
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """Acknowledge an active alert."""
    engine = AlertEngine(db)
    try:
        alert = engine.acknowledge_alert(alert_id, username=current_user.username if current_user else "Administrator")
        return ApiResponse(success=True, data=AlertResponse.model_validate(alert), message="Alert acknowledged")
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/{alert_id}/resolve", response_model=ApiResponse[AlertResponse])
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "operator"]))
):
    """Resolve an alert."""
    engine = AlertEngine(db)
    try:
        alert = engine.resolve_alert(alert_id)
        return ApiResponse(success=True, data=AlertResponse.model_validate(alert), message="Alert resolved")
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/rules", response_model=ApiResponse[List[AlertRuleResponse]])
def list_alert_rules(db: Session = Depends(get_db)):
    """List all configured alert rules."""
    rules = db.query(AlertRule).order_by(AlertRule.id.asc()).all()
    return ApiResponse(
        success=True,
        data=[AlertRuleResponse.model_validate(r) for r in rules],
        message=f"Retrieved {len(rules)} alert rules"
    )


@router.post("/rules", response_model=ApiResponse[AlertRuleResponse], status_code=status.HTTP_201_CREATED)
def create_alert_rule(
    request: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"]))
):
    """Create a new alert rule."""
    existing = db.query(AlertRule).filter(AlertRule.name == request.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Alert rule '{request.name}' already exists")

    rule = AlertRule(
        name=request.name,
        rule_type=request.rule_type,
        severity=request.severity,
        threshold_value=request.threshold_value,
        is_enabled=request.is_enabled,
        description=request.description
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return ApiResponse(success=True, data=AlertRuleResponse.model_validate(rule), message="Alert rule created")

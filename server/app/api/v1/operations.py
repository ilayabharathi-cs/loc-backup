"""Operations Center REST API router for RetroVault V10."""

import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.security.dependencies import get_current_user
from app.schemas.v10_schemas import (
    SystemHealthResponse,
    MetricIngestRequest,
    MetricSampleResponse,
    AlertTriggerRequest,
    AlertAcknowledgeRequest,
    AlertResolveRequest,
    AlertResponse,
    IncidentCorrelateRequest,
    IncidentUpdateRequest,
    IncidentResponse,
    RecommendationResponse
)
from app.services.observability.health_service import HealthCheckService
from app.services.observability.metrics_collector import MetricsCollector
from app.services.observability.alert_evaluator import AlertEvaluator
from app.services.observability.incident_service import IncidentService
from app.services.observability.recommendations import RecommendationEngine

router = APIRouter(prefix="/operations", tags=["Operations Center"])


@router.get("/health", response_model=SystemHealthResponse)
def get_system_health(
    check_type: str = "deep_health",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve explainable rule-based system health across all 14 infrastructure components."""
    service = HealthCheckService(db)
    return service.evaluate_all(check_type=check_type)


@router.get("/metrics")
def get_operational_metrics(
    collect_live: bool = False,
    metric_name: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Query operational metrics or trigger on-demand live system sampling."""
    collector = MetricsCollector(db)
    if collect_live:
        return collector.collect_live_system_metrics()
    samples = collector.query_metrics(metric_name=metric_name, source=source, limit=limit, offset=offset)
    return [
        {
            "id": s.id,
            "metric_name": s.metric_name,
            "value": s.value,
            "timestamp": s.timestamp.isoformat(),
            "source": s.source,
            "labels": json.loads(s.labels_json) if s.labels_json else None,
            "granularity": s.granularity
        }
        for s in samples
    ]


@router.post("/metrics")
def record_operational_metric(
    payload: MetricIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Record an operational metric sample."""
    collector = MetricsCollector(db)
    sample = collector.record_metric(
        metric_name=payload.metric_name,
        value=payload.value,
        source=payload.source,
        labels=payload.labels,
        granularity=payload.granularity
    )
    return {"status": "SUCCESS", "metric_id": sample.id}


@router.get("/alerts", response_model=List[AlertResponse])
def list_operational_alerts(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = None,
    alert_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List deduplicated operational alerts."""
    evaluator = AlertEvaluator(db)
    alerts = evaluator.list_alerts(status=status_filter, severity=severity, alert_type=alert_type, limit=limit, offset=offset)
    return [
        AlertResponse(
            id=a.id,
            alert_id=a.alert_id,
            alert_type=a.alert_type,
            severity=a.severity,
            status=a.status,
            source=a.source,
            resource_id=a.resource_id,
            title=a.title,
            message=a.message,
            occurrence_count=a.occurrence_count,
            first_seen_at=a.first_seen_at.isoformat(),
            last_seen_at=a.last_seen_at.isoformat(),
            incident_id=a.incident_id
        )
        for a in alerts
    ]


@router.post("/alerts", response_model=AlertResponse)
def trigger_operational_alert(
    payload: AlertTriggerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger or deduplicate an operational alert."""
    evaluator = AlertEvaluator(db)
    a = evaluator.trigger_alert(
        alert_type=payload.alert_type,
        resource_id=payload.resource_id,
        source=payload.source,
        title=payload.title,
        message=payload.message,
        severity=payload.severity,
        threshold_value=payload.threshold_value,
        observed_value=payload.observed_value,
        evidence=payload.evidence
    )
    return AlertResponse(
        id=a.id,
        alert_id=a.alert_id,
        alert_type=a.alert_type,
        severity=a.severity,
        status=a.status,
        source=a.source,
        resource_id=a.resource_id,
        title=a.title,
        message=a.message,
        occurrence_count=a.occurrence_count,
        first_seen_at=a.first_seen_at.isoformat(),
        last_seen_at=a.last_seen_at.isoformat(),
        incident_id=a.incident_id
    )


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledgeRequest = AlertAcknowledgeRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Acknowledge an active operational alert."""
    evaluator = AlertEvaluator(db)
    user_name = payload.acknowledged_by or current_user.username
    a = evaluator.acknowledge_alert(alert_id, user_name)
    if not a:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return AlertResponse(
        id=a.id,
        alert_id=a.alert_id,
        alert_type=a.alert_type,
        severity=a.severity,
        status=a.status,
        source=a.source,
        resource_id=a.resource_id,
        title=a.title,
        message=a.message,
        occurrence_count=a.occurrence_count,
        first_seen_at=a.first_seen_at.isoformat(),
        last_seen_at=a.last_seen_at.isoformat(),
        incident_id=a.incident_id
    )


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: str,
    payload: AlertResolveRequest = AlertResolveRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resolve an operational alert."""
    evaluator = AlertEvaluator(db)
    user_name = payload.resolved_by or current_user.username
    a = evaluator.resolve_alert(alert_id, user_name)
    if not a:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return AlertResponse(
        id=a.id,
        alert_id=a.alert_id,
        alert_type=a.alert_type,
        severity=a.severity,
        status=a.status,
        source=a.source,
        resource_id=a.resource_id,
        title=a.title,
        message=a.message,
        occurrence_count=a.occurrence_count,
        first_seen_at=a.first_seen_at.isoformat(),
        last_seen_at=a.last_seen_at.isoformat(),
        incident_id=a.incident_id
    )


@router.get("/incidents", response_model=List[IncidentResponse])
def list_operational_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List correlated operational incidents."""
    service = IncidentService(db)
    incidents = service.list_incidents(status=status_filter, severity=severity, limit=limit, offset=offset)
    return [
        IncidentResponse(
            incident_id=inc.incident_id,
            title=inc.title,
            status=inc.status,
            severity=inc.severity,
            root_event=inc.root_event,
            relationship_type=inc.relationship_type,
            affected_resources=json.loads(inc.affected_resources_json or "[]"),
            child_alerts=json.loads(inc.child_alerts_json or "[]"),
            timeline=json.loads(inc.timeline_json or "[]"),
            created_at=inc.created_at.isoformat(),
            updated_at=inc.updated_at.isoformat(),
            resolved_at=inc.resolved_at.isoformat() if inc.resolved_at else None
        )
        for inc in incidents
    ]


@router.post("/incidents", response_model=IncidentResponse)
def correlate_operational_incident(
    payload: IncidentCorrelateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Correlate multiple operational alerts into a unified incident."""
    service = IncidentService(db)
    inc = service.correlate_alerts(
        root_event=payload.root_event,
        title=payload.title,
        alert_ids=payload.alert_ids,
        affected_resources=payload.affected_resources,
        severity=payload.severity,
        relationship_type=payload.relationship_type,
        evidence=payload.evidence
    )
    return IncidentResponse(
        incident_id=inc.incident_id,
        title=inc.title,
        status=inc.status,
        severity=inc.severity,
        root_event=inc.root_event,
        relationship_type=inc.relationship_type,
        affected_resources=json.loads(inc.affected_resources_json or "[]"),
        child_alerts=json.loads(inc.child_alerts_json or "[]"),
        timeline=json.loads(inc.timeline_json or "[]"),
        created_at=inc.created_at.isoformat(),
        updated_at=inc.updated_at.isoformat(),
        resolved_at=inc.resolved_at.isoformat() if inc.resolved_at else None
    )


@router.put("/incidents/{incident_id}", response_model=IncidentResponse)
def update_incident_status(
    incident_id: str,
    payload: IncidentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update incident status and timeline."""
    service = IncidentService(db)
    inc = service.update_incident_status(incident_id, payload.status, current_user.username, payload.note)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return IncidentResponse(
        incident_id=inc.incident_id,
        title=inc.title,
        status=inc.status,
        severity=inc.severity,
        root_event=inc.root_event,
        relationship_type=inc.relationship_type,
        affected_resources=json.loads(inc.affected_resources_json or "[]"),
        child_alerts=json.loads(inc.child_alerts_json or "[]"),
        timeline=json.loads(inc.timeline_json or "[]"),
        created_at=inc.created_at.isoformat(),
        updated_at=inc.updated_at.isoformat(),
        resolved_at=inc.resolved_at.isoformat() if inc.resolved_at else None
    )


@router.get("/recommendations", response_model=List[RecommendationResponse])
def get_operational_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve explainable, evidence-backed operational recommendations."""
    engine = RecommendationEngine(db)
    recs = engine.evaluate_recommendations()
    return [RecommendationResponse(**r) for r in recs]

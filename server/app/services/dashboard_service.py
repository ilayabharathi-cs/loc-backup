import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.client import Client
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.storage_repository import StorageRepository
from app.models.audit_log import AuditLog
from app.schemas.dashboard import DashboardSummaryResponse
from app.schemas.job import JobResponse
from app.schemas.activity import AuditLogResponse

def get_dashboard_summary(db: Session) -> DashboardSummaryResponse:
    total_clients = db.query(Client).count()
    online_clients = db.query(Client).filter(Client.status == "active").count()
    offline_clients = db.query(Client).filter(Client.status == "offline").count()
    pending_clients = db.query(Client).filter(Client.status == "pending").count()

    successful_backups = db.query(BackupRun).filter(BackupRun.status == "completed").count()
    failed_backups = db.query(BackupRun).filter(BackupRun.status == "failed").count()
    running_backups = db.query(BackupRun).filter(BackupRun.status == "running").count()

    # Storage metrics from repositories or actual filesystem
    storage = db.query(StorageRepository).first()
    tb_factor = 1024 ** 4
    if storage and storage.total_bytes:
        storage_total = round(storage.total_bytes / tb_factor, 1)
        storage_used = round(storage.used_bytes / tb_factor, 1)
        storage_available = round(storage.available_bytes / tb_factor, 1)
    else:
        try:
            from app.services.repository.local import get_repository
            health = get_repository().validate_storage_health()
            if health.get("total_bytes"):
                storage_total = round(health["total_bytes"] / tb_factor, 1)
                storage_used = round(health["used_bytes"] / tb_factor, 1)
                storage_available = round(health["free_bytes"] / tb_factor, 1)
            else:
                storage_total = 0.0
                storage_used = 0.0
                storage_available = 0.0
        except Exception:
            storage_total = 0.0
            storage_used = 0.0
            storage_available = 0.0

    # Failed jobs in last 24h
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now_utc - datetime.timedelta(hours=24)
    failed_jobs_last_24h = db.query(BackupJob).filter(
        BackupJob.status == "failed",
        BackupJob.created_at >= cutoff
    ).count()

    # Real Average RPO estimation (from most recent valid recovery points)
    from app.models.recovery_point import RecoveryPoint
    recent_rps = db.query(RecoveryPoint).filter(
        RecoveryPoint.status.in_(["valid", "completed"])
    ).order_by(RecoveryPoint.created_at.desc()).limit(10).all()
    if recent_rps:
        diffs = [
            (now_utc - (rp.created_at if (rp.created_at and rp.created_at.tzinfo) else (rp.created_at.replace(tzinfo=datetime.timezone.utc) if rp.created_at else now_utc))).total_seconds()
            for rp in recent_rps
        ]
        average_rpo_seconds = max(0, int(sum(diffs) / len(diffs)))
    else:
        average_rpo_seconds = 0

    # Recent jobs (limit 7)
    recent_jobs_db = db.query(BackupJob).order_by(BackupJob.created_at.desc()).limit(7).all()
    recent_jobs: list[JobResponse] = []
    for j in recent_jobs_db:
        processed_mb = 0.0
        progress = 100 if j.status == "completed" else 0
        latest_run = db.query(BackupRun).filter(BackupRun.job_id == j.id).order_by(BackupRun.started_at.desc()).first()
        if latest_run:
            processed_mb = round(latest_run.bytes_processed / (1024 * 1024), 1)
            if latest_run.status == "completed":
                progress = 100
            elif latest_run.status == "running":
                if latest_run.bytes_total > 0:
                    progress = min(99, max(1, int((latest_run.bytes_uploaded / latest_run.bytes_total) * 100)))
                elif latest_run.files_discovered > 0:
                    progress = min(99, max(1, int((latest_run.files_uploaded / latest_run.files_discovered) * 100)))
                else:
                    progress = 5
            elif latest_run.status in ("failed", "cancelled"):
                progress = 0

        recent_jobs.append(JobResponse(
            id=j.id,
            job_id=j.job_id,
            client_id=j.client_id,
            client_identifier=j.client.client_id if j.client else str(j.client_id),
            client_hostname=j.client.hostname if j.client else f"Client-{j.client_id}",
            policy_id=j.policy_id,
            policy_name=j.policy.name if j.policy else "Default Policy",
            status=j.status,
            scheduled_at=j.scheduled_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
            created_at=j.created_at,
            data_processed_mb=processed_mb,
            progress_percent=progress
        ))

    # Recent activity logs (limit 10)
    recent_logs_db = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(10).all()
    recent_activity: list[AuditLogResponse] = []
    for l in recent_logs_db:
        sev = "INFO"
        if "FAILED" in l.action or "ERROR" in l.action:
            sev = "ERROR"
        elif "WARNING" in l.action or "BREACH" in l.action or "DISABLE" in l.action:
            sev = "WARNING"

        recent_activity.append(AuditLogResponse(
            id=l.id,
            user_id=l.user_id,
            username=l.user.username if l.user else "SYSTEM",
            client_id=l.client_id,
            client_identifier=l.client.client_id if l.client else None,
            action=l.action,
            resource_type=l.resource_type,
            resource_id=l.resource_id,
            ip_address=l.ip_address,
            details=l.details,
            created_at=l.created_at,
            severity=sev
        ))

    return DashboardSummaryResponse(
        total_clients=total_clients,
        online_clients=online_clients,
        offline_clients=offline_clients,
        pending_clients=pending_clients,
        successful_backups=successful_backups,
        failed_backups=failed_backups,
        running_backups=running_backups,
        storage_total=storage_total,
        storage_used=storage_used,
        storage_available=storage_available,
        average_rpo_seconds=average_rpo_seconds,
        failed_jobs_last_24h=failed_jobs_last_24h,
        recent_jobs=recent_jobs,
        recent_activity=recent_activity
    )

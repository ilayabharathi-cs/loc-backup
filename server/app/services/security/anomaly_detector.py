"""Anomaly and Ransomware Detection Engine for RetroVault V8.

Evaluates backup run metrics against historical baselines and security profiles.
Computes multi-signal weighted scores and triggers non-destructive SECURITY_HOLD.
"""

import datetime
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.backup_run import BackupRun
from app.models.recovery_point import RecoveryPoint
from app.models.client import Client
from app.models.security_v8_models import SecurityEvent, SecurityProfile, SecurityIncident
from app.services.security.entropy_analyzer import EntropyAnalyzer

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Evaluates backup runs for ransomware indicators and triggers protection workflows."""

    # Configurable weights for anomaly signals
    SIGNAL_WEIGHTS = {
        "MASS_MODIFICATION": 25,
        "UNUSUAL_CREATION_RATE": 15,
        "UNUSUAL_DELETION_RATE": 25,
        "EXTENSION_TRANSFORMATION": 30,
        "HIGH_ENTROPY": 30,
        "COMPRESSION_COLLAPSE": 20,
        "SIZE_INFLATION": 15,
    }

    def __init__(self, db: Session):
        self.db = db

    def evaluate_backup_run(
        self,
        run_id: int,
        files_metadata: Optional[List[Dict[str, Any]]] = None,
        custom_threshold: Optional[int] = None
    ) -> Dict[str, Any]:
        """Analyzes a completed or active backup run for anomalies.
        
        Args:
            run_id: ID of the backup run to evaluate.
            files_metadata: Optional list of file dicts containing path, size, entropy, action, etc.
            custom_threshold: Optional score threshold override (default 60).
        """
        run = self.db.query(BackupRun).filter(BackupRun.id == run_id).first()
        if not run:
            return {"error": f"BackupRun {run_id} not found", "score": 0, "anomalous": False}

        client = self.db.query(Client).filter(Client.id == run.client_id).first()
        
        # Load security profile if client has group or default
        profile = self._get_security_profile_for_client(client)
        threshold = custom_threshold if custom_threshold is not None else (profile.anomaly_threshold if profile else 60)
        entropy_limit = profile.entropy_threshold if profile else 7.2

        signals_triggered: List[Dict[str, Any]] = []
        total_score = 0

        # Retrieve historical averages for this client's previous runs
        historical_stats = self._get_historical_averages(run.client_id, exclude_run_id=run.id)

        # 1. Mass Modification Signal
        files_modified = getattr(run, "files_modified", 0) or 0
        avg_modified = historical_stats.get("avg_modified", 0)
        if avg_modified > 0 and files_modified >= (avg_modified * 3) and files_modified >= 10:
            weight = self.SIGNAL_WEIGHTS["MASS_MODIFICATION"]
            total_score += weight
            signals_triggered.append({
                "signal": "MASS_MODIFICATION",
                "weight": weight,
                "detail": f"Modified files ({files_modified}) is {files_modified / avg_modified:.1f}x historical average ({avg_modified:.1f})"
            })
        elif files_modified > 100 and avg_modified == 0:
            weight = self.SIGNAL_WEIGHTS["MASS_MODIFICATION"] // 2
            total_score += weight
            signals_triggered.append({
                "signal": "MASS_MODIFICATION",
                "weight": weight,
                "detail": f"High modified file count ({files_modified}) with no prior baseline"
            })

        # 2. Unusual Deletion Rate Signal
        files_deleted = getattr(run, "files_deleted", 0) or 0
        total_previous_files = historical_stats.get("avg_total_files", 1) or 1
        deletion_pct = (files_deleted / max(total_previous_files, 1)) * 100.0
        if deletion_pct >= 20.0 and files_deleted >= 5:
            weight = self.SIGNAL_WEIGHTS["UNUSUAL_DELETION_RATE"]
            total_score += weight
            signals_triggered.append({
                "signal": "UNUSUAL_DELETION_RATE",
                "weight": weight,
                "detail": f"Deletion rate {deletion_pct:.1f}% ({files_deleted} files) exceeds safe threshold (20%)"
            })

        # 3. Compression Collapse (Encrypted files fail to compress)
        # If files were processed, check compression ratio
        orig_bytes = getattr(run, "bytes_processed", 0) or 0
        stored_bytes = getattr(run, "bytes_uploaded", 0) or getattr(run, "bytes_transferred", 0) or 0
        if orig_bytes > 500000 and stored_bytes > 0:
            ratio = stored_bytes / orig_bytes
            # If ratio is close to 1.0 or > 0.98 on normally compressible types
            if ratio >= 0.98 and files_modified > 5:
                weight = self.SIGNAL_WEIGHTS["COMPRESSION_COLLAPSE"]
                total_score += weight
                signals_triggered.append({
                    "signal": "COMPRESSION_COLLAPSE",
                    "weight": weight,
                    "detail": f"Compression ratio collapsed to {ratio:.2f} (near-zero compressibility indicates encrypted data)"
                })

        # 4. File-level inspection (Entropy, Ransomware Extensions, Transformations)
        suspicious_extensions_found = []
        high_entropy_files = []

        if files_metadata:
            for f in files_metadata:
                path = f.get("path") or f.get("filename", "")
                ent = f.get("entropy")
                if ent is None and "bytes" in f:
                    ent = EntropyAnalyzer.calculate_shannon_entropy(f["bytes"])
                
                if ent is not None:
                    eval_res = EntropyAnalyzer.evaluate_file_entropy(
                        filename=path,
                        entropy=ent,
                        entropy_threshold=entropy_limit
                    )
                    if eval_res["is_suspicious"]:
                        high_entropy_files.append({
                            "path": path,
                            "entropy": ent,
                            "reasons": eval_res["reasons"]
                        })

                # Check extension transformation or known ransomware extension
                ext = ("." + path.rsplit(".", 1)[-1].lower()) if "." in path else ""
                if ext in EntropyAnalyzer.SUSPICIOUS_RANSOM_EXTENSIONS:
                    suspicious_extensions_found.append({"path": path, "extension": ext})

        if suspicious_extensions_found:
            weight = self.SIGNAL_WEIGHTS["EXTENSION_TRANSFORMATION"]
            total_score += weight
            signals_triggered.append({
                "signal": "EXTENSION_TRANSFORMATION",
                "weight": weight,
                "count": len(suspicious_extensions_found),
                "samples": [x["path"] for x in suspicious_extensions_found[:5]],
                "detail": f"Detected {len(suspicious_extensions_found)} files with known ransomware extension markers"
            })

        if high_entropy_files:
            weight = self.SIGNAL_WEIGHTS["HIGH_ENTROPY"]
            total_score += weight
            signals_triggered.append({
                "signal": "HIGH_ENTROPY",
                "weight": weight,
                "count": len(high_entropy_files),
                "samples": [f"{x['path']} (entropy={x['entropy']})" for x in high_entropy_files[:5]],
                "detail": f"Detected {len(high_entropy_files)} high-entropy files exceeding {entropy_limit} baseline"
            })

        # Cap score at 100
        total_score = min(total_score, 100)
        is_anomalous = total_score >= threshold

        # Record findings and take actions if anomalous
        event = None
        recovery_point = self.db.query(RecoveryPoint).filter(RecoveryPoint.backup_run_id == run.id).first()

        if is_anomalous:
            severity = "CRITICAL" if total_score >= 80 else ("HIGH" if total_score >= 60 else "MEDIUM")
            description = (
                f"Ransomware/Anomaly alert: Backup Run #{run.id} scored {total_score}/100 "
                f"(threshold: {threshold}) with {len(signals_triggered)} trigger signals."
            )
            evidence = {
                "run_id": run.id,
                "client_id": run.client_id,
                "total_score": total_score,
                "threshold": threshold,
                "signals": signals_triggered,
                "suspicious_extensions": suspicious_extensions_found[:20],
                "high_entropy_samples": high_entropy_files[:20],
            }

            event = SecurityEvent(
                event_type="RANSOMWARE_SUSPECTED" if (suspicious_extensions_found or high_entropy_files) else "ANOMALY_DETECTED",
                severity=severity,
                client_id=run.client_id,
                repository_id=getattr(run, "repository_id", None),
                run_id=run.id,
                recovery_point_id=recovery_point.id if recovery_point else None,
                score=total_score,
                description=description,
                evidence_json=json.dumps(evidence),
                status="OPEN"
            )
            self.db.add(event)

            # Apply NON-DESTRUCTIVE SECURITY_HOLD on the recovery point
            if recovery_point:
                recovery_point.protection_state = "SECURITY_HOLD"
                recovery_point.protected_reason = f"Anomaly score {total_score} exceeds threshold {threshold}"
                recovery_point.protected_by = "ANOMALY_DETECTOR"
                recovery_point.protection_created_at = datetime.datetime.now(datetime.timezone.utc)
                recovery_point.security_hold_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
                logger.warning(
                    f"Applied SECURITY_HOLD to RecoveryPoint #{recovery_point.id} due to anomaly score {total_score}"
                )

            # Automatically create or escalate to SecurityIncident if critical
            if total_score >= 70:
                incident_number = f"INC-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')}-{run.id}"
                existing_inc = self.db.query(SecurityIncident).filter(SecurityIncident.incident_number == incident_number).first()
                if not existing_inc:
                    inc = SecurityIncident(
                        incident_number=incident_number,
                        title=f"Potential Ransomware Incident on Client #{run.client_id} (Run #{run.id})",
                        severity=severity,
                        status="DETECTED",
                        client_id=run.client_id,
                        candidate_recovery_point_id=recovery_point.id if recovery_point else None,
                        containment_notes=f"Auto-generated incident from AnomalyDetector. Score: {total_score}."
                    )
                    self.db.add(inc)

            self.db.commit()

        return {
            "run_id": run.id,
            "client_id": run.client_id,
            "score": total_score,
            "threshold": threshold,
            "anomalous": is_anomalous,
            "signals": signals_triggered,
            "event_id": event.id if event else None,
            "security_hold_applied": bool(recovery_point and recovery_point.protection_state == "SECURITY_HOLD"),
        }

    def _get_security_profile_for_client(self, client: Optional[Client]) -> Optional[SecurityProfile]:
        """Resolves security profile for client via client_group or default."""
        if not client:
            return self.db.query(SecurityProfile).filter(SecurityProfile.is_default == True).first()
        
        if getattr(client, "group_id", None):
            from app.models.security_v8_models import ClientGroup
            group = self.db.query(ClientGroup).filter(ClientGroup.id == client.group_id).first()
            if group and group.security_profile_id:
                prof = self.db.query(SecurityProfile).filter(SecurityProfile.id == group.security_profile_id).first()
                if prof:
                    return prof
        
        return self.db.query(SecurityProfile).filter(SecurityProfile.is_default == True).first()

    def _get_historical_averages(self, client_id: int, exclude_run_id: int) -> Dict[str, float]:
        """Calculates historical averages of files modified, files total, etc. for a client."""
        runs = (
            self.db.query(BackupRun)
            .filter(BackupRun.client_id == client_id, BackupRun.id != exclude_run_id, BackupRun.status == "completed")
            .order_by(BackupRun.id.desc())
            .limit(5)
            .all()
        )
        if not runs:
            return {"avg_modified": 0.0, "avg_total_files": 0.0}

        mod_counts = [getattr(r, "files_modified", 0) or 0 for r in runs]
        total_counts = [getattr(r, "files_total", 0) or 0 for r in runs]

        return {
            "avg_modified": sum(mod_counts) / len(mod_counts),
            "avg_total_files": sum(total_counts) / len(total_counts),
        }

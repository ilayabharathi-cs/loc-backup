"""3-2-1 Backup Protection Topology Calculator for RetroVault V7."""

from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.storage_repository import StorageRepository
from app.models.replication import ReplicationJob


class BackupTopologyEvaluator:
    """Evaluates whether the storage repository topology meets the 3-2-1 backup rule."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_topology(self) -> Dict[str, Any]:
        """
        Calculates:
        1. 3 copies of data (primary + secondary + tertiary/offsite)
        2. 2 different storage media / repository types
        3. 1 offsite / remote repository
        """
        repos = self.db.query(StorageRepository).filter(
            StorageRepository.status.in_(["ONLINE", "online", "MAINTENANCE", "READ_ONLY"])
        ).all()

        total_repos = len(repos)
        repo_types = set()
        has_offsite = False
        offsite_repos = []
        primary_repos = []
        secondary_repos = []

        for r in repos:
            t = (r.repository_type or "LOCAL_FILESYSTEM").upper()
            repo_types.add(t)

            is_remote = t in ("REMOTE", "REMOTE_FILESYSTEM", "S3", "S3_COMPATIBLE", "OBJECT_STORAGE", "NAS", "SMB")
            if is_remote or (r.endpoint and "http" in r.endpoint.lower()):
                has_offsite = True
                offsite_repos.append(r.name)
            elif not primary_repos:
                primary_repos.append(r.name)
            else:
                secondary_repos.append(r.name)

        # Check for active completed replications
        completed_replications = self.db.query(ReplicationJob).filter(
            ReplicationJob.status == "COMPLETED"
        ).count()

        # Copies calculation
        copies_count = min(3, total_repos) if completed_replications > 0 or total_repos <= 1 else total_repos
        media_types_count = len(repo_types)

        missing_requirements: List[str] = []
        if total_repos < 3:
            missing_requirements.append(f"Requires 3 repository targets, but only {total_repos} configured")
        if media_types_count < 2:
            missing_requirements.append(f"Requires at least 2 distinct storage media types, found {media_types_count} ({', '.join(repo_types) or 'None'})")
        if not has_offsite:
            missing_requirements.append("Requires at least 1 offsite or remote repository target (e.g. S3-compatible or remote server)")

        is_compliant = (total_repos >= 3 and media_types_count >= 2 and has_offsite)

        return {
            "status": "COMPLIANT" if is_compliant else "NOT COMPLIANT",
            "is_compliant": is_compliant,
            "total_repositories": total_repos,
            "total_copies": copies_count,
            "media_types": list(repo_types),
            "media_types_count": media_types_count,
            "has_offsite": has_offsite,
            "offsite_repositories": offsite_repos,
            "primary_repositories": primary_repos,
            "secondary_repositories": secondary_repos,
            "completed_replications": completed_replications,
            "missing_requirements": missing_requirements,
            "recommendation": "3-2-1 backup protection rules satisfied." if is_compliant else "To satisfy 3-2-1: Configure at least 1 Primary Local, 1 Secondary Local/NAS, and 1 Offsite/S3-Compatible repository."
        }

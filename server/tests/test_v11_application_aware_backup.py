"""Tests for RetroVault V11 Application-Aware Backup Execution and CAS Integration."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import uuid
import datetime
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.workload_v11_models import Workload, WorkloadArtifact, ApplicationConsistencyRecord, BackupChain
from app.models.storage_object import StorageObject
from app.models.client import Client
from app.services.workload.discovery_service import WorkloadDiscoveryService
from app.services.workload.protection_service import WorkloadProtectionService


def test_workload_discovery_and_protection_flow():
    db = SessionLocal()
    try:
        # 1. Ensure test client
        client_stmt = select(Client).order_by(Client.id.asc())
        client = db.execute(client_stmt).scalars().first()
        client_id = str(client.id) if client else "1"

        # 2. Workload Discovery
        discovery = WorkloadDiscoveryService(db)
        discovered = discovery.discover_client_workloads(
            client_id=client_id,
            provider_type="MSSQL",
            config={"instance": "MSSQLSERVER", "databases": ["TestAppDB"], "exclude_databases": []}
        )
        assert len(discovered) >= 1
        workload = discovered[0]
        assert "mssql" in workload.workload_id

        # 3. Workload Backup Execution
        prot_service = WorkloadProtectionService(db)
        backup_res = prot_service.execute_workload_backup(
            workload_id=workload.workload_id,
            backup_type="FULL",
            initiated_by="TEST_RUNNER"
        )
        assert backup_res["success"] is True
        assert backup_res["status"] == "COMPLETED"
        assert backup_res["consistency_state"] == "APPLICATION_CONSISTENT"
        assert backup_res["artifacts_count"] >= 1
        assert backup_res["total_bytes"] > 0

        # 4. Verify CAS StorageObject
        art_stmt = select(WorkloadArtifact).where(
            WorkloadArtifact.recovery_point_id == str(backup_res["recovery_point_id"])
        )
        arts = db.execute(art_stmt).scalars().all()
        assert len(arts) >= 1
        art = arts[0]
        assert art.storage_object_id is not None

        so_stmt = select(StorageObject).where(StorageObject.object_id == art.storage_object_id)
        so = db.execute(so_stmt).scalars().first()
        assert so is not None
        assert so.content_sha256 == art.checksum_sha256
        assert so.state == "AVAILABLE"

        # 5. Verify Application Consistency Record
        acr_stmt = select(ApplicationConsistencyRecord).where(
            ApplicationConsistencyRecord.workload_id == workload.workload_id
        )
        acr = db.execute(acr_stmt).scalars().first()
        assert acr is not None
        assert acr.consistency_state == "APPLICATION_CONSISTENT"
        assert acr.verified_by == "TEST_RUNNER"

        # 6. Verify Backup Chain Creation
        chain_stmt = select(BackupChain).where(BackupChain.workload_id == workload.workload_id)
        chain = db.execute(chain_stmt).scalars().first()
        assert chain is not None
        assert chain.status == "VALID"
        assert chain.chain_length >= 1

    finally:
        db.close()

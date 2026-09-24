import pytest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.cluster_v9_models import DistributedJob, ClusterNode, ClusterLease
from app.services.cluster.node_service import NodeHeartbeatService
from app.services.cluster.orphan_recovery import OrphanRecoveryService
from app.services.cluster.cluster_reconciliation import ClusterReconciliationService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_orphan_job_recovery_when_worker_offline(db_session):
    node_svc = NodeHeartbeatService(db_session)
    node = node_svc.register_node("crashed-worker", "host-crash", "10.0.0.50", 8000, ["WORKER"])

    # Simulate running job on this worker
    now = datetime.datetime.now(datetime.timezone.utc)
    job = DistributedJob(
        job_type="BACKUP",
        priority="NORMAL",
        priority_weight=3,
        status="RUNNING",
        owner_node_id="crashed-worker",
        started_at=now - datetime.timedelta(seconds=60),
        heartbeat_at=now - datetime.timedelta(seconds=60),
        attempt_count=1,
        max_attempts=3,
    )
    db_session.add(job)
    db_session.commit()

    # Worker goes OFFLINE
    node.status = "OFFLINE"
    db_session.commit()

    orphan_svc = OrphanRecoveryService(db_session)
    summary = orphan_svc.scan_and_recover_orphaned_jobs(heartbeat_timeout_seconds=30)

    assert summary["orphaned_count"] == 1
    assert summary["requeued_count"] == 1
    assert job.id in summary["recovered_job_ids"]

    # Verify job was reset to QUEUED with cleared owner
    db_session.refresh(job)
    assert job.status == "QUEUED"
    assert job.owner_node_id is None


def test_cluster_reconciliation_safeguard(db_session):
    now = datetime.datetime.now(datetime.timezone.utc)
    # Set up leadership lease for leader-1
    lease = ClusterLease(
        lease_key="LEADER_ELECTION",
        owner_node_id="leader-1",
        lease_token="tok-1",
        lease_expires_at=now + datetime.timedelta(seconds=30),
    )
    db_session.add(lease)
    db_session.commit()

    # Non-leader node attempts reconciliation -> blocked by split-brain guard
    non_leader_reconciler = ClusterReconciliationService(db_session, leader_node_id="imposter-node")
    res_blocked = non_leader_reconciler.reconcile_cluster(force=False)
    assert res_blocked["reconciled"] is False
    assert "not the active leader" in res_blocked["reason"]

    # Active leader successfully executes reconciliation
    leader_reconciler = ClusterReconciliationService(db_session, leader_node_id="leader-1")
    res_success = leader_reconciler.reconcile_cluster(force=False)
    assert res_success["reconciled"] is True
    assert res_success["leader_node_id"] == "leader-1"

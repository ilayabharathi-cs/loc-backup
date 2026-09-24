import pytest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.cluster_v9_models import DistributedJob, ClusterNode
from app.services.cluster.distributed_queue import DistributedJobQueue
from app.services.cluster.worker_pool import RepositoryWorkerPool
from app.services.cluster.node_service import NodeHeartbeatService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_distributed_queue_priority_and_atomic_claim(db_session):
    # Register worker node
    node_svc = NodeHeartbeatService(db_session)
    node_svc.register_node("worker-1", "host-w1", "10.0.0.10", 8000, ["WORKER"])

    queue = DistributedJobQueue(db_session)

    # Enqueue a NORMAL job first, then a CRITICAL job
    job_normal = queue.enqueue_job(job_type="BACKUP", priority="NORMAL", client_id="client-1")
    job_critical = queue.enqueue_job(job_type="BACKUP", priority="CRITICAL", client_id="client-2")

    assert job_normal.priority_weight == 10
    assert job_critical.priority_weight == 1

    # Claim next job: worker-1 should receive CRITICAL job first despite being enqueued second
    claimed_1 = queue.claim_next_job(worker_node_id="worker-1")
    assert claimed_1 is not None
    assert claimed_1.id == job_critical.id
    assert claimed_1.status == "CLAIMED"
    assert claimed_1.owner_node_id == "worker-1"

    # Claim next job: worker-1 receives the NORMAL job
    claimed_2 = queue.claim_next_job(worker_node_id="worker-1")
    assert claimed_2 is not None
    assert claimed_2.id == job_normal.id

    # Queue is now empty of queued jobs
    claimed_3 = queue.claim_next_job(worker_node_id="worker-1")
    assert claimed_3 is None

    # Heartbeat and complete
    hb_ok = queue.heartbeat_job(claimed_1.id, progress_percent=50.0, status_message="Halfway done")
    assert hb_ok is True

    comp_ok = queue.complete_job(claimed_1.id, status="COMPLETED")
    assert comp_ok is True
    assert claimed_1.status == "COMPLETED"


def test_worker_pool_backpressure(db_session):
    queue = DistributedJobQueue(db_session)
    pool = RepositoryWorkerPool(db_session)

    # Evaluate on empty queue
    bp_initial = pool.evaluate_backpressure()
    assert bp_initial["queued_jobs"] == 0
    assert bp_initial["backpressure_level"] in ["NORMAL", "HIGH", "CRITICAL"]

    # Enqueue 15 jobs
    for i in range(15):
        queue.enqueue_job(job_type="BACKUP", priority="NORMAL")

    bp_after = pool.evaluate_backpressure()
    assert bp_after["queued_jobs"] == 15
    assert bp_after["backpressure_level"] in ["MODERATE", "HIGH", "CRITICAL"]

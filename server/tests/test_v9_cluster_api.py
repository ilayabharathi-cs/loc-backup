import pytest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_cluster_node_and_leader_api(client):
    # 1. Register Node
    res = client.post("/api/v1/cluster/nodes/register", json={
        "node_id": "test-node-1",
        "hostname": "test-box-1",
        "ip_address": "127.0.0.1",
        "port": 8000,
        "roles": ["CONTROL_PLANE", "WORKER"]
    })
    assert res.status_code == 200
    data = res.json()
    assert data["node_id"] == "test-node-1"
    assert data["status"] in ["ACTIVE", "HEALTHY"]

    # 2. Node Heartbeat
    hb_res = client.post("/api/v1/cluster/nodes/test-node-1/heartbeat", json={
        "current_load": 15.5,
        "active_jobs_count": 1
    })
    assert hb_res.status_code == 200
    assert hb_res.json()["status"] == "HEARTBEAT_ACK"

    # 3. Leader Election
    elect_res = client.post("/api/v1/cluster/leader/elect", json={
        "node_id": "test-node-1",
        "ttl_seconds": 15
    })
    assert elect_res.status_code == 200
    assert elect_res.json()["is_leader"] is True

    # 4. Get Leader
    leader_res = client.get("/api/v1/cluster/leader")
    assert leader_res.status_code == 200
    assert leader_res.json()["leader_node_id"] == "test-node-1"

    # 5. Distributed Lock Acquire & Release
    lock_res = client.post("/api/v1/cluster/locks/acquire", json={
        "resource_key": "test:resource:key",
        "owner_node_id": "test-node-1",
        "ttl_seconds": 30
    })
    assert lock_res.status_code == 200
    lock_data = lock_res.json()
    assert lock_data["acquired"] is True
    token = lock_data["token"]

    rel_res = client.post("/api/v1/cluster/locks/release", json={
        "resource_key": "test:resource:key",
        "lock_token": token
    })
    assert rel_res.status_code == 200
    assert rel_res.json()["released"] is True

    # 6. Cluster Status
    status_res = client.get("/api/v1/cluster/status")
    assert status_res.status_code == 200
    st_data = status_res.json()
    assert "cluster_status" in st_data
    assert st_data["active_nodes"] >= 1


def test_distributed_scheduler_and_bulk_api(client):
    # 1. Enqueue job
    enq_res = client.post("/api/v1/scheduler/jobs", json={
        "job_type": "BACKUP",
        "priority": "HIGH",
        "client_id": "client-test-99"
    })
    assert enq_res.status_code == 200
    job = enq_res.json()
    assert job["id"] is not None
    assert job["job_type"] == "BACKUP"
    assert job["priority"] == "HIGH"
    job_id = job["id"]

    # 2. Claim job
    claim_res = client.post("/api/v1/scheduler/jobs/claim", json={
        "worker_node_id": "test-node-1",
        "supported_job_types": ["BACKUP"]
    })
    assert claim_res.status_code == 200
    claimed = claim_res.json()
    assert claimed is not None
    claimed_id = claimed["id"]
    assert claimed["status"] == "CLAIMED"

    # 3. Complete job
    comp_res = client.post(f"/api/v1/scheduler/jobs/{claimed_id}/complete", json={
        "status": "COMPLETED"
    })
    assert comp_res.status_code == 200
    assert comp_res.json()["completed"] is True

    # 4. Worker pools info
    pools_res = client.get("/api/v1/scheduler/pools")
    assert pools_res.status_code == 200
    assert "categories" in pools_res.json()
    assert "backpressure" in pools_res.json()

import pytest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.cluster_v9_models import ClusterNode, ClusterLease, ClusterEvent
from app.services.cluster.leader_election import LeaderElectionService
from app.services.cluster.node_service import NodeHeartbeatService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_leader_election_lifecycle(db_session):
    node_svc = NodeHeartbeatService(db_session)
    node_svc.register_node("node-1", "host-1", "10.0.0.1", 8000, ["CONTROL_PLANE"])
    node_svc.register_node("node-2", "host-2", "10.0.0.2", 8000, ["CONTROL_PLANE"])

    election_svc = LeaderElectionService(db_session)

    # 1. Initially no leader
    leader_info = election_svc.get_current_leader()
    assert leader_info["leader_node_id"] is None
    assert leader_info["is_active"] is False

    # 2. Node 1 acquires leadership
    res1 = election_svc.try_acquire_or_renew_leadership("node-1", ttl_seconds=10)
    assert res1["is_leader"] is True
    assert res1["leader_node_id"] == "node-1"
    assert res1["action"] == "ACQUIRED"

    # Verify leader state
    leader_info = election_svc.get_current_leader()
    assert leader_info["leader_node_id"] == "node-1"
    assert leader_info["is_active"] is True

    # 3. Node 2 attempts to acquire while Node 1 is active -> DENIED
    res2 = election_svc.try_acquire_or_renew_leadership("node-2", ttl_seconds=10)
    assert res2["is_leader"] is False
    assert res2["action"] == "DENIED"
    assert res2["leader_node_id"] == "node-1"

    # 4. Node 1 renews lease
    res1_renew = election_svc.try_acquire_or_renew_leadership("node-1", ttl_seconds=15)
    assert res1_renew["is_leader"] is True
    assert res1_renew["action"] == "RENEWED"

    # 5. Node 1 voluntarily resigns
    res_resign = election_svc.resign_leadership("node-1")
    assert res_resign["resigned"] is True

    # 6. Node 2 can now immediately acquire leadership
    res2_takeover = election_svc.try_acquire_or_renew_leadership("node-2", ttl_seconds=10)
    assert res2_takeover["is_leader"] is True
    assert res2_takeover["leader_node_id"] == "node-2"

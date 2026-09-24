import pytest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.cluster_v9_models import DistributedLock
from app.services.cluster.lock_service import DistributedLockService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_distributed_lock_lifecycle(db_session):
    lock_svc = DistributedLockService(db_session)
    res_key = "repo:local-primary:backup"

    # 1. Acquire lock
    acq1 = lock_svc.acquire_lock(res_key, owner_node_id="node-a", ttl_seconds=5)
    assert acq1["acquired"] is True
    token = acq1["token"]
    assert token is not None
    assert lock_svc.is_locked(res_key) is True

    # 2. Competing node fails to acquire active lock
    acq2 = lock_svc.acquire_lock(res_key, owner_node_id="node-b", ttl_seconds=5)
    assert acq2["acquired"] is False
    assert acq2["owner_node_id"] == "node-a"

    # 3. Renew lock
    renewed = lock_svc.renew_lock(res_key, lock_token=token, ttl_seconds=10)
    assert renewed is True

    # Wrong token fails renewal
    assert lock_svc.renew_lock(res_key, lock_token="bad-token") is False

    # 4. Release lock
    released = lock_svc.release_lock(res_key, lock_token=token)
    assert released is True
    assert lock_svc.is_locked(res_key) is False

    acq3 = lock_svc.acquire_lock(res_key, owner_node_id="node-b", ttl_seconds=5)
    assert acq3["acquired"] is True
    assert acq3.get("token") is not None

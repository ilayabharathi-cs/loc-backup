"""Tests for RetroVault V11 Policy Lifecycle Orchestration."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import uuid
import pytest

from app.database.session import SessionLocal
from app.services.workload.policy_orchestrator import (
    PolicyOrchestrationService,
    LIFECYCLE_DRAFT,
    LIFECYCLE_APPROVED,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_RETIRED
)


def test_policy_lifecycle_versioning_and_rollback():
    db = SessionLocal()
    try:
        svc = PolicyOrchestrationService(db)
        policy_id = f"pol-test-{uuid.uuid4().hex[:6]}"

        # 1. Create v1 DRAFT
        def_v1 = {"schedule": "0 2 * * *", "retention_days": 30, "backup_type": "FULL"}
        v1 = svc.create_policy_version(policy_id, def_v1, created_by="ADMIN")
        assert v1.version == 1
        assert v1.lifecycle_state == LIFECYCLE_DRAFT

        # 2. Approve v1
        v1_approved = svc.approve_policy_version(v1.id, approver="SEC_OFFICER", notes="Approved initial draft")
        assert v1_approved.lifecycle_state == LIFECYCLE_APPROVED

        # 3. Activate v1
        v1_active = svc.activate_policy_version(v1.id, activated_by="ADMIN")
        assert v1_active.lifecycle_state == LIFECYCLE_ACTIVE
        assert v1_active.effective_at is not None

        # 4. Create and activate v2
        def_v2 = {"schedule": "0 4 * * *", "retention_days": 60, "backup_type": "FULL"}
        v2 = svc.create_policy_version(policy_id, def_v2, created_by="ADMIN")
        assert v2.version == 2
        svc.approve_policy_version(v2.id, approver="SEC_OFFICER")
        v2_active = svc.activate_policy_version(v2.id, activated_by="ADMIN")
        assert v2_active.lifecycle_state == LIFECYCLE_ACTIVE

        # Check v1 was automatically RETIRED upon v2 activation
        db.refresh(v1)
        assert v1.lifecycle_state == LIFECYCLE_RETIRED

        # 5. Rollback policy to v1 configuration
        v3_rollback = svc.rollback_policy(policy_id, target_version=1, rolled_back_by="ADMIN")
        assert v3_rollback.version == 3
        assert v3_rollback.lifecycle_state == LIFECYCLE_ACTIVE
        assert "retention_days\": 30" in v3_rollback.definition_json

        # 6. Deterministic affected resources calculation
        affected = svc.calculate_affected_resources(policy_id)
        assert "affected_workload_count" in affected
        assert "affected_client_count" in affected

    finally:
        db.close()

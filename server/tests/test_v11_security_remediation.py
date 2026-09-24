"""Tests for RetroVault V11 Safe Remediation, Approval Gates, and Dependency Graph Safety."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

from app.database.session import SessionLocal
from app.services.workload.remediation_service import RemediationService
from app.services.workload.dependency_graph import DependencyGraphEngine
from app.models.workload_v11_models import RemediationAction


def test_safe_remediation_and_security_invariants():
    db = SessionLocal()
    try:
        svc = RemediationService(db)

        # 1. Prohibited autonomous destructive action MUST raise PermissionError
        with pytest.raises(PermissionError) as exc_info:
            svc.propose_remediation(
                action_type="DELETE_RECOVERY_POINT",
                target_resource_type="recovery_point",
                target_resource_id="100",
                proposed_by="AUTONOMOUS_BOT"
            )
        assert "Autonomous destructive action" in str(exc_info.value)

        # 2. Permitted safe remediation
        rem = svc.propose_remediation(
            action_type="REENABLE_PROTECTION",
            target_resource_type="workload",
            target_resource_id="wl-test-01",
            proposed_by="ADMIN",
            requires_dual_approval=True
        )
        assert rem.status == "PENDING_APPROVAL"
        assert rem.requires_dual_approval is True

        # 3. Dual-approval enforcement: Same user cannot approve twice
        with pytest.raises(PermissionError) as dual_err:
            svc.approve_remediation(rem.remediation_id, approver="ADMIN")
            svc.approve_remediation(rem.remediation_id, approver="ADMIN")
        assert "Dual approval requirement" in str(dual_err.value)

        # Second distinct approver approves
        approved_rem = svc.approve_remediation(rem.remediation_id, approver="SECURITY_LEAD")
        assert approved_rem.status == "APPROVED"

        # 4. Execute approved remediation
        exec_res = svc.execute_remediation(rem.remediation_id, executor="SYSTEM")
        assert exec_res["success"] is True

        # 5. Dependency Graph safety check
        dep_engine = DependencyGraphEngine(db)
        dep_engine.register_dependency("POLICY", "pol-1", "WORKLOAD", "wl-1")
        deps = dep_engine.get_dependencies_for("POLICY", "pol-1")
        assert len(deps) >= 1
        assert deps[0]["child_id"] == "wl-1"

    finally:
        db.close()

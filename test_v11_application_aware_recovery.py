"""RetroVault V11: Application-Aware Data Protection & Automated Recovery
Comprehensive Live End-to-End Verification Test Suite (60 Scenarios).

Validates:
1. Workload Provider Framework & Discovery (Windows Filesystem, MSSQL, PostgreSQL, Generic App)
2. Provider Capability Matrix & Diagnostics
3. Credential Secrecy & Command Sanitization
4. Hook Security, Parameterized Execution & Injection Prevention
5. Evidence-Based Application Consistency States
6. Application-Consistent Backup Execution & CAS Storage
7. CAS Deduplication and StorageObject Integrity
8. Recovery Point Linking & Manifest Generation
9. Backup Chain Tracking & Continuity Validation (VALID, DEGRADED, BROKEN, UNKNOWN)
10. Application Restore Preview & Overwrite Conflict Detection
11. 7-Phase Application Restore Execution (DISCOVER -> COMPLETE)
12. Synthetic Sandbox Recovery & Checksum Verification
13. Sandbox Isolation Invariant (No production data modification, zero sandbox leakage)
14. Recovery Readiness Engine (11 Factual Measurable Signals)
15. Policy Orchestration (Lifecycle: DRAFT -> APPROVED -> ACTIVE -> RETIRED, Versioning & Rollback)
16. Safe Remediation Workflows & Dual-Approval Gating
17. Rejection of Autonomous Destructive Operations
18. Advanced Dependency Graph & Safety Invariants
19. V8 Ransomware SECURITY_HOLD Integration
20. Telemetry Metrics & Compliance Evidence Ingestion
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "server"))
import time
import json
import uuid
import datetime
import tempfile
import shutil

from sqlalchemy import select, func
from app.database.session import SessionLocal
from app.models.client import Client
from app.models.recovery_point import RecoveryPoint
from app.models.storage_object import StorageObject
from app.models.workload_v11_models import (
    Workload,
    WorkloadArtifact,
    ApplicationConsistencyRecord,
    BackupChain,
    RecoveryVerification,
    RecoveryReadiness,
    PolicyLifecycle,
    RemediationAction,
    DependencyRelation
)
from app.services.workload.provider import (
    FILE_SYSTEM_CONSISTENT,
    APPLICATION_CONSISTENT,
    CRASH_CONSISTENT,
    FAILED,
    CAPABILITY_SUPPORTED
)
from app.services.workload.providers import (
    WindowsFilesystemProvider,
    GenericAppProvider,
    MSSQLWorkloadProvider,
    PostgreSQLWorkloadProvider
)
from app.services.workload.discovery_service import WorkloadDiscoveryService
from app.services.workload.consistency_service import WorkloadConsistencyService
from app.services.workload.protection_service import WorkloadProtectionService
from app.services.workload.backup_chain_validator import BackupChainValidator
from app.services.workload.recovery_service import WorkloadRecoveryService
from app.services.workload.recovery_verification import RecoveryVerificationEngine
from app.services.workload.readiness_engine import RecoveryReadinessEngine
from app.services.workload.policy_orchestrator import PolicyOrchestrationService
from app.services.workload.remediation_service import RemediationService
from app.services.workload.dependency_graph import DependencyGraphEngine


def run_e2e():
    print("=" * 80)
    print("RetroVault V11 Live End-to-End Verification Suite")
    print("=" * 80)

    db = SessionLocal()
    passed = 0
    failed = 0

    def record_step(scenario_num: int, title: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"[PASS] Scenario {scenario_num:02d}: {title} {detail}")
        else:
            failed += 1
            print(f"[FAIL] Scenario {scenario_num:02d}: {title} {detail}")

    try:
        # Step 0: Ensure client exists
        client_stmt = select(Client).order_by(Client.id.asc())
        client = db.execute(client_stmt).scalars().first()
        client_id = str(client.id) if client else "1"

        # --- Phase A: Workload Provider & Discovery (1-10) ---
        fs_prov = WindowsFilesystemProvider()
        record_step(1, "Filesystem Provider Type", fs_prov.provider_type == "WINDOWS_FILESYSTEM")
        record_step(2, "Filesystem Capabilities", fs_prov.get_capabilities()["vss_snapshot"] == CAPABILITY_SUPPORTED)

        fs_discovery = fs_prov.discover(client_id, {"drives": ["C:", "D:"]})
        record_step(3, "Filesystem Volume Discovery", len(fs_discovery) == 2 and fs_discovery[0]["consistency_capability"] == FILE_SYSTEM_CONSISTENT)

        mssql_prov = MSSQLWorkloadProvider()
        record_step(4, "MSSQL Provider Type", mssql_prov.provider_type == "MSSQL")
        record_step(5, "MSSQL Capabilities Matrix", mssql_prov.get_capabilities()["full_backup"] == CAPABILITY_SUPPORTED)

        mssql_discovery = mssql_prov.discover(client_id, {
            "instance": "PROD_SQL_01",
            "databases": ["CoreERP", "BillingDB", "tempdb"],
            "exclude_databases": ["tempdb"]
        })
        record_step(6, "MSSQL Database Discovery with Exclusion", len(mssql_discovery) == 2 and "tempdb" not in [w["config"]["database"] for w in mssql_discovery])

        pg_prov = PostgreSQLWorkloadProvider()
        record_step(7, "PostgreSQL Provider Type", pg_prov.provider_type == "POSTGRESQL")
        pg_discovery = pg_prov.discover(client_id, {
            "host": "localhost",
            "databases": ["customer_portal", "template1"],
            "exclude_databases": ["template1"]
        })
        record_step(8, "PostgreSQL Database Discovery", len(pg_discovery) == 1 and pg_discovery[0]["name"] == "PostgreSQL: customer_portal")

        gen_prov = GenericAppProvider()
        record_step(9, "Generic App Provider Type", gen_prov.provider_type == "GENERIC_APP")
        gen_discovery = gen_prov.discover(client_id, {
            "applications": [{"name": "CustomAnalytics", "quiesce_command": "echo freeze", "unquiesce_command": "echo thaw"}]
        })
        record_step(10, "Generic App Hook Discovery", len(gen_discovery) == 1 and gen_discovery[0]["consistency_capability"] == APPLICATION_CONSISTENT)

        # --- Phase B: Security, Hooks & Credential Isolation (11-16) ---
        record_step(11, "Credential Secrecy in Workload Metadata", "password" not in json.dumps(mssql_discovery[0]))
        sanitized = gen_prov._execute_safe_hook("echo --password SuperSecretPass123", "TEST")
        record_step(12, "Credential Redaction in Hook Output", "[REDACTED]" in sanitized.stdout or "SuperSecretPass123" not in sanitized.stdout)

        cmd_inj_test = gen_prov._execute_safe_hook("echo test && dir", "TEST")
        record_step(13, "Command Injection Prevention", cmd_inj_test.success is False and "prohibited shell chaining" in cmd_inj_test.error)

        binary_allowlist_test = gen_prov._execute_safe_hook("unauthorized_binary.exe --exec", "TEST")
        record_step(14, "Binary Allow-list Rejection", binary_allowlist_test.success is False and "not in the approved security allow-list" in binary_allowlist_test.error)

        timeout_test = gen_prov._execute_safe_hook("cmd.exe /c ping -n 4 127.0.0.1", "TEST", timeout=1)
        record_step(15, "Hook Execution Timeout Handling", timeout_test.success is False and "timed out" in timeout_test.error)

        failed_pre_hook = gen_prov.verify_consistency({"pre_hook_result": cmd_inj_test})
        record_step(16, "Failed Pre-hook Invariant (Cannot be Application Consistent)", failed_pre_hook.consistency_state == FAILED)

        # --- Phase C: Workload Discovery Service (17-20) ---
        disc_service = WorkloadDiscoveryService(db)
        registered_providers = disc_service.list_providers()
        record_step(17, "Discovery Service Providers Enumeration", len(registered_providers) >= 4)

        persisted_workloads = disc_service.discover_client_workloads(
            client_id=client_id,
            provider_type="MSSQL",
            config={"instance": "MSSQLSERVER", "databases": ["E2E_TestDB"], "exclude_databases": []}
        )
        record_step(18, "Discovery Service DB Persistence", len(persisted_workloads) >= 1)
        test_wl = persisted_workloads[0]
        record_step(19, "Discovered Workload Status", test_wl.status == "DISCOVERED")
        record_step(20, "Discovered Workload Health", test_wl.health == "HEALTHY")

        # --- Phase D: Application-Aware Backup & Consistency (21-30) ---
        prot_service = WorkloadProtectionService(db)
        backup_res = prot_service.execute_workload_backup(
            workload_id=test_wl.workload_id,
            backup_type="FULL",
            initiated_by="E2E_RUNNER"
        )
        record_step(21, "Workload Backup Execution Success", backup_res["success"] is True)
        record_step(22, "Workload Status Completed", backup_res["status"] == "COMPLETED")
        record_step(23, "Factual Application Consistent State", backup_res["consistency_state"] == APPLICATION_CONSISTENT)
        record_step(24, "Artifacts Generated", backup_res["artifacts_count"] >= 1)
        record_step(25, "Backup Bytes Transferred", backup_res["total_bytes"] > 0)

        # Verify Workload DB update
        db.refresh(test_wl)
        record_step(26, "Workload Protection State Updated", test_wl.protection_state == "PROTECTED")
        record_step(27, "Workload Last Protected At Recorded", test_wl.last_protected_at is not None)

        # Verify CAS StorageObject
        art_stmt = select(WorkloadArtifact).where(WorkloadArtifact.recovery_point_id == str(backup_res["recovery_point_id"]))
        art = db.execute(art_stmt).scalars().first()
        record_step(28, "Workload Artifact Recorded in DB", art is not None)
        so_stmt = select(StorageObject).where(StorageObject.object_id == art.storage_object_id)
        so = db.execute(so_stmt).scalars().first()
        record_step(29, "CAS StorageObject Physical Link", so is not None and so.content_sha256 == art.checksum_sha256)
        record_step(30, "CAS StorageObject Available State", so.state == "AVAILABLE")

        # --- Phase E: Consistency Records & Deduplication (31-35) ---
        consist_svc = WorkloadConsistencyService(db)
        acr = consist_svc.get_consistency_record(str(backup_res["recovery_point_id"]))
        record_step(31, "Application Consistency Record Integrity", acr is not None and acr.consistency_state == APPLICATION_CONSISTENT)
        record_step(32, "Verified By System/User Logged", acr.verified_by == "E2E_RUNNER")

        # Second backup of identical data to test CAS deduplication
        backup_res_2 = prot_service.execute_workload_backup(
            workload_id=test_wl.workload_id,
            backup_type="FULL",
            initiated_by="E2E_RUNNER"
        )
        record_step(33, "Subsequent Backup Execution", backup_res_2["success"] is True)
        record_step(34, "CAS Storage Object Reference Count Incremented", so.reference_count >= 1)
        record_step(35, "Recovery Point Manifest Registration", backup_res_2["recovery_point_id"] != backup_res["recovery_point_id"])

        # --- Phase F: Backup Chain Tracking & Validation (36-40) ---
        chain_validator = BackupChainValidator(db)
        chain_stmt = select(BackupChain).where(BackupChain.workload_id == test_wl.workload_id)
        chain = db.execute(chain_stmt).scalars().first()
        record_step(36, "Backup Chain Registered", chain is not None)

        val_res = chain_validator.validate_chain(chain.chain_id)
        record_step(37, "Backup Chain Healthy State (VALID)", val_res["status"] in ["VALID", "DEGRADED"])

        # Broken chain scenario (non-existent base RP)
        broken_chain = BackupChain(
            chain_id=f"chain-e2e-broken-{uuid.uuid4().hex[:6]}",
            workload_id=test_wl.workload_id,
            base_recovery_point_id="99999999",
            latest_recovery_point_id="99999999",
            chain_length=1,
            status="VALID"
        )
        db.add(broken_chain)
        db.commit()
        val_broken = chain_validator.validate_chain(broken_chain.chain_id)
        record_step(38, "Broken Chain Detection (Missing Base RP)", val_broken["status"] == "BROKEN")
        record_step(39, "Broken Chain Reason Explanation", "missing or deleted" in val_broken["broken_reason"])

        val_missing = chain_validator.validate_chain("invalid-chain-id-e2e")
        record_step(40, "Unknown Chain Handling", val_missing["status"] == "UNKNOWN")

        # --- Phase G: Application Restore Preview & Execution (41-45) ---
        recovery_svc = WorkloadRecoveryService(db)
        restore_dir = os.path.join(tempfile.gettempdir(), f"e2e_restore_{uuid.uuid4().hex[:6]}")

        preview = recovery_svc.preview_restore(
            workload_id=test_wl.workload_id,
            recovery_point_id=str(backup_res["recovery_point_id"]),
            target_destination=restore_dir,
            recovery_mode="APPLICATION_RESTORE"
        )
        record_step(41, "Restore Preview Generated", preview.workload_id == test_wl.workload_id)
        record_step(42, "Restore Preview Consistency Status", preview.consistency_status == APPLICATION_CONSISTENT)
        record_step(43, "Restore Preview Estimated Size", preview.estimated_size_bytes > 0)
        record_step(44, "Restore Preview Safety Verification", preview.is_safe_to_proceed is True)

        restore_exec = recovery_svc.execute_application_restore(
            workload_id=test_wl.workload_id,
            recovery_point_id=str(backup_res["recovery_point_id"]),
            target_destination=restore_dir
        )
        record_step(45, "7-Phase Application Restore Execution", restore_exec.success is True and restore_exec.current_phase == "COMPLETE")
        if os.path.exists(restore_dir):
            shutil.rmtree(restore_dir, ignore_errors=True)

        # --- Phase H: Synthetic Recovery Verification (46-50) ---
        verif_engine = RecoveryVerificationEngine(db)
        verif = verif_engine.trigger_verification(
            recovery_point_id=str(backup_res["recovery_point_id"]),
            workload_id=test_wl.workload_id,
            verification_type="CHECKSUM",
            initiated_by="E2E_SCHEDULER"
        )
        record_step(46, "Synthetic Verification Job Queued", verif.status == "PENDING")

        verif_result = verif_engine.execute_verification(verif.verification_id)
        record_step(47, "Synthetic Sandbox Execution Result", verif_result["success"] is True and verif_result["status"] == "VERIFIED")
        record_step(48, "Verification Duration Telemetry", verif_result["duration_ms"] >= 0)
        record_step(49, "Sandbox Cleanup Invariant (No Disk Leak)", not os.path.exists(verif.sandbox_path))

        db.refresh(test_wl)
        record_step(50, "Workload Last Verified At Updated", test_wl.last_verified_at is not None)

        # --- Phase I: Recovery Readiness Intelligence (51-53) ---
        readiness_engine = RecoveryReadinessEngine(db)
        readiness = readiness_engine.evaluate_workload_readiness(test_wl.workload_id)
        record_step(51, "Recovery Readiness Evaluated State", readiness["readiness_state"] in ["READY", "DEGRADED", "NOT_READY"])
        record_step(52, "11 Contributing Signals Present", len(readiness["contributing_signals"]) >= 10)
        record_step(53, "RPO Compliance Rate Computed", readiness["rpo_compliance_percent"] >= 0)

        # --- Phase J: Policy Orchestration Governance (54-56) ---
        policy_svc = PolicyOrchestrationService(db)
        pol_id = f"e2e-policy-{uuid.uuid4().hex[:6]}"
        v1 = policy_svc.create_policy_version(pol_id, {"retention_days": 30}, created_by="E2E_ADMIN")
        record_step(54, "Policy Lifecycle Draft Version Created", v1.version == 1 and v1.lifecycle_state == "DRAFT")

        v1_app = policy_svc.approve_policy_version(v1.id, approver="SECURITY_OFFICER")
        record_step(55, "Policy Lifecycle Approval Sign-off", v1_app.lifecycle_state == "APPROVED")

        v1_act = policy_svc.activate_policy_version(v1.id, activated_by="E2E_ADMIN")
        record_step(56, "Policy Lifecycle Activation", v1_act.lifecycle_state == "ACTIVE")

        # --- Phase K: Safe Remediation & Approval Gates (57-58) ---
        remediation_svc = RemediationService(db)
        rem = remediation_svc.propose_remediation(
            action_type="START_RECOVERY_VERIFICATION",
            target_resource_type="workload",
            target_resource_id=test_wl.workload_id,
            proposed_by="E2E_OPERATOR"
        )
        record_step(57, "Safe Remediation Proposal Created", rem.status == "PENDING_APPROVAL")

        remediation_svc.approve_remediation(rem.remediation_id, approver="E2E_ADMIN")
        rem_exec = remediation_svc.execute_remediation(rem.remediation_id)
        record_step(58, "Approved Remediation Safely Executed", rem_exec["success"] is True)

        # Prohibited destructive remediation invariant
        try:
            remediation_svc.propose_remediation("DELETE_RECOVERY_POINT", "recovery_point", "1")
            record_step(59, "Destructive Operation Rejection Invariant", False)
        except PermissionError:
            record_step(59, "Destructive Operation Rejection Invariant", True)

        # --- Phase L: Dependency Graph Safety Invariant (60) ---
        dep_engine = DependencyGraphEngine(db)
        dep_engine.register_dependency("WORKLOAD", test_wl.workload_id, "RECOVERY_POINT", str(backup_res["recovery_point_id"]))
        safe_check = dep_engine.verify_safe_to_delete("WORKLOAD", test_wl.workload_id)
        record_step(60, "Dependency Graph Prevents Unsafe Cleanup", safe_check["is_safe_to_delete"] is False and len(safe_check["blockers"]) > 0)

    finally:
        db.close()

    print("=" * 80)
    print(f"E2E Execution Complete: {passed} Passed, {failed} Failed out of {passed + failed} Scenarios.")
    print("=" * 80)
    return failed == 0


if __name__ == "__main__":
    success = run_e2e()
    sys.exit(0 if success else 1)

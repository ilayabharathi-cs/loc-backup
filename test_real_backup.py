"""Script to verify real local full backup engine against live backend."""

import os
import sys
import json
import hashlib

# Ensure imports work
sys.path.insert(0, os.path.abspath("."))

from agent.src.config import AgentConfig
from agent.src.identity import DeviceIdentity
from agent.src.api_client import BackendApiClient
from agent.src.policy_resolver import ResolvedPolicy
from agent.src.backup.backup_engine import BackupEngine


def setup_test_files():
    base_dir = os.path.abspath("test_real_backup_dir")
    docs_dir = os.path.join(base_dir, "docs")
    proj_dir = os.path.join(base_dir, "projects")
    os.makedirs(docs_dir, exist_ok=True)
    os.makedirs(proj_dir, exist_ok=True)

    f1 = os.path.join(docs_dir, "report.txt")
    f2 = os.path.join(docs_dir, "budget.csv")
    f3 = os.path.join(proj_dir, "core_spec.md")

    with open(f1, "w", encoding="utf-8") as f:
        f.write("Quarterly Backup Audit Report 1995")
    with open(f2, "w", encoding="utf-8") as f:
        f.write("id,item,cost\n1,tapes,500\n2,drives,1200\n")
    with open(f3, "w", encoding="utf-8") as f:
        f.write("# RetroVault Core Spec V2 Initial Full File Backup Engine\n")

    files = [f1, f2, f3]
    hashes = {}
    for fp in files:
        with open(fp, "rb") as f:
            hashes[fp] = hashlib.sha256(f.read()).hexdigest()

    print(f"Created 3 test files in {base_dir}:")
    for fp, h in hashes.items():
        print(f"  {os.path.basename(fp)} -> SHA256: {h}")
    return base_dir, hashes


def main():
    test_dir, expected_hashes = setup_test_files()

    config = AgentConfig(server_url="http://127.0.0.1:8000")
    identity = DeviceIdentity()
    api_client = BackendApiClient(config)

    # 1. Register agent if needed
    if not identity.client_id:
        from agent.src.system_info import collect_system_info
        sys_info = collect_system_info(identity.device_id, config.agent_version)
        reg_data = api_client.register_agent(sys_info)
        identity.set_registration(reg_data["client_id"])

    print(f"Using Client ID: {identity.client_id}, Device ID: {identity.device_id}")

    # 2. Build Policy pointing to test_dir
    policy = ResolvedPolicy(
        policy_id=1,
        policy_name="Real Full Backup Test Policy",
        valid_paths=[test_dir],
        excluded_paths=[]
    )

    # 3. Execute Full Backup
    engine = BackupEngine(config, identity, api_client)
    summary = engine.run_full_backup(policy)

    print("\n" + "=" * 50)
    print("BACKUP SUMMARY:")
    print(json.dumps({
        "run_id": summary.run_id,
        "client_id": summary.client_id,
        "status": summary.status,
        "files_discovered": summary.files_discovered,
        "files_uploaded": summary.files_uploaded,
        "files_failed": summary.files_failed,
        "bytes_total": summary.bytes_total,
        "bytes_uploaded": summary.bytes_uploaded,
        "duration_seconds": summary.duration_seconds,
        "recovery_point_created": summary.recovery_point_created
    }, indent=2))
    print("=" * 50)

    # 4. Verify in Backend Database
    import httpx
    client = httpx.Client(base_url="http://127.0.0.1:8000/api/v1")
    r_files = client.get(f"/backups/files?run_id={summary.run_id}")
    backed_up_files = r_files.json()["data"]
    print(f"\nFiles recorded in database for run {summary.run_id}: {len(backed_up_files)}")
    for bf in backed_up_files:
        print(f"  ID: {bf['id']} | Name: {bf['file_name']} | Size: {bf['size_bytes']} | Object: {bf['storage_object']} | SHA: {bf['sha256'][:16]}...")
        assert bf["sha256"] in expected_hashes.values(), f"Hash mismatch for {bf['file_name']}"

    # Verify recovery point
    r_pts = client.get(f"/backups/recovery-points?client_id={summary.client_id}")
    pts = r_pts.json()["data"]
    matching_pt = [p for p in pts if p["backup_run_id"] == summary.run_id]
    print(f"\nRecovery Points found for run {summary.run_id}: {len(matching_pt)}")
    assert len(matching_pt) == 1, "Recovery point was not created!"
    print(f"  Point ID: {matching_pt[0]['id']}, Files: {matching_pt[0]['files_count']}, Size: {matching_pt[0]['total_size_bytes']} bytes, Status: {matching_pt[0]['status']}")

    print("\n>>> ALL REAL BACKUP VERIFICATION CHECKS PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    main()

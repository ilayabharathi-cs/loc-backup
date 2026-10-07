import sqlite3
import os
import shutil
from pathlib import Path

workspace_root = Path(__file__).parent.resolve()
db_paths = [
    workspace_root / "server" / "backup.db",
    workspace_root / "backup.db"
]

tables_to_clear = [
    "clients",
    "backup_jobs",
    "backup_runs",
    "backup_files",
    "recovery_points",
    "upload_sessions",
    "upload_chunks",
    "backup_checkpoints",
    "run_events",
    "restore_jobs",
    "restore_items",
    "restore_checkpoints",
    "storage_objects",
    "audit_logs",
    "alerts",
    "operational_alerts",
    "operational_incidents",
    "security_events",
    "security_incidents",
    "security_simulations",
    "deletion_guards",
    "dr_tests",
    "workloads",
    "compliance_evidence",
    "compliance_reports",
    "report_executions",
    "capacity_snapshots",
    "capacity_forecasts",
    "metric_samples",
    "health_checks",
    "garbage_collection_jobs",
    "garbage_collection_items",
    "integrity_scans",
    "application_consistency_records",
    "recovery_readiness_records",
    "policy_lifecycles",
    "policy_approvals",
    "remediation_actions",
    "dependency_relations",
    "cloud_offloaded_objects",
    "virtual_recovery_hydration_items",
    "virtual_recovery_sessions",
    "storage_tiers",
    "cloud_credentials"
]

for dbp in db_paths:
    if not dbp.exists():
        continue
    print(f"Cleaning database: {dbp}")
    conn = sqlite3.connect(str(dbp))
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF;")
    
    # Check existing tables
    existing_tables = set(r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())

    for t in tables_to_clear:
        if t in existing_tables:
            try:
                cur.execute(f'DELETE FROM "{t}"')
                print(f"  [+] Cleared {t}")
            except Exception as e:
                print(f"  [-] Error clearing {t}: {e}")

    # Reset test policies, keeping only default standard policies (1, 2, 3)
    if "backup_policies" in existing_tables:
        try:
            cur.execute('DELETE FROM "backup_policies" WHERE id NOT IN (1, 2, 3)')
            if "backup_policy_paths" in existing_tables:
                cur.execute('DELETE FROM "backup_policy_paths" WHERE policy_id NOT IN (1, 2, 3)')
            print("  [+] Cleaned test policies (retained standard policies 1, 2, 3)")
        except Exception as e:
            print(f"  [-] Error cleaning test policies: {e}")

    # Reset storage repositories, keeping only Repo 1 (Local-CAS-Repository)
    if "storage_repositories" in existing_tables:
        try:
            cur.execute('DELETE FROM "storage_repositories" WHERE id != 1')
            repo_path = str(workspace_root / "repository")
            cur.execute('''
                UPDATE "storage_repositories" 
                SET path = ?, used_bytes = 0 
                WHERE id = 1
            ''', (repo_path,))
            print(f"  [+] Reset storage_repositories: Local-CAS-Repository -> {repo_path}")
        except Exception as e:
            print(f"  [-] Error resetting storage_repositories: {e}")

    conn.commit()
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.execute("VACUUM;")
    conn.commit()

    # Report results
    if "clients" in existing_tables:
        c_count = cur.execute('SELECT COUNT(*) FROM clients').fetchone()[0]
        print(f"  [*] Clients remaining: {c_count}")
    if "backup_jobs" in existing_tables:
        j_count = cur.execute('SELECT COUNT(*) FROM backup_jobs').fetchone()[0]
        print(f"  [*] Backup jobs remaining: {j_count}")

    conn.close()

# Clean physical repository storage files
repo_dir = workspace_root / "repository"
for sub in ["objects", "clients", "quarantine", "temp", "cache"]:
    p = repo_dir / sub
    if p.exists():
        for item in p.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception as e:
                print(f"Could not remove {item}: {e}")
print("[SUCCESS] Local repository objects and clients directories are empty and clean.")

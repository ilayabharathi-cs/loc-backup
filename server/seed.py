import sys
import os
import datetime
from sqlalchemy.orm import Session

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.connection import engine
from app.database.base import Base
from app.database.session import SessionLocal
from app.models.user import User
from app.models.client import Client
from app.models.backup_policy import BackupPolicy, BackupPolicyPath
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.recovery_point import RecoveryPoint
from app.models.storage_repository import StorageRepository
from app.models.audit_log import AuditLog
from app.security.password import hash_password

def seed_database():
    print("[*] Initializing database tables...")
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # 1. Seed Users
        if db.query(User).count() == 0:
            print("[+] Seeding default users (admin, operator, viewer)...")
            admin = User(
                username="admin",
                email="admin@retrovault.corp",
                password_hash=hash_password("AdminPass123!"),
                role="admin",
                is_active=True
            )
            operator = User(
                username="operator",
                email="operator@retrovault.corp",
                password_hash=hash_password("Operator123!"),
                role="operator",
                is_active=True
            )
            viewer = User(
                username="viewer",
                email="viewer@retrovault.corp",
                password_hash=hash_password("Viewer123!"),
                role="viewer",
                is_active=True
            )
            db.add_all([admin, operator, viewer])
            db.commit()

        # 2. Seed Storage Repositories (Dynamic Path & Real Disk Capacity)
        if db.query(StorageRepository).count() == 0:
            import shutil
            from app.config import settings
            print("[+] Seeding primary storage repository...")
            repo_path = settings.get_repository_root()
            try:
                total_b, used_b, free_b = shutil.disk_usage(repo_path)
            except Exception:
                tb_bytes = 1024 ** 4
                total_b = 10 * tb_bytes
                free_b = 10 * tb_bytes

            repo = StorageRepository(
                name="Local-CAS-Repository",
                repository_type="local",
                path=repo_path,
                total_bytes=total_b,
                used_bytes=0,
                available_bytes=free_b,
                status="online"
            )
            db.add(repo)
            db.commit()

        # 3. Seed Backup Policies
        if db.query(BackupPolicy).count() == 0:
            print("[+] Seeding enterprise backup policies...")
            pol1 = BackupPolicy(
                name="Windows User Data",
                description="Standard enterprise workstation policy safeguarding universal user directories",
                backup_type="incremental",
                change_detection="usn_journal",
                rpo_target_seconds=120,
                compression_enabled=True,
                encryption_enabled=True,
                cpu_limit_percent=10,
                network_limit_mbps=100,
                retention_days=7,
                is_active=True
            )
            pol2 = BackupPolicy(
                name="Finance Sensitive Vault",
                description="High-frequency encrypted backup with strict RPO and immutable retention",
                backup_type="incremental",
                change_detection="usn_journal",
                rpo_target_seconds=60,
                compression_enabled=True,
                encryption_enabled=True,
                cpu_limit_percent=15,
                network_limit_mbps=150,
                retention_days=30,
                is_active=True
            )
            pol3 = BackupPolicy(
                name="Developer Workstation",
                description="Code repository backup with aggressive build-artifact exclusions",
                backup_type="incremental",
                change_detection="usn_journal",
                rpo_target_seconds=120,
                compression_enabled=True,
                encryption_enabled=True,
                cpu_limit_percent=20,
                network_limit_mbps=200,
                retention_days=14,
                is_active=True
            )
            db.add_all([pol1, pol2, pol3])
            db.flush()

            # Universal paths
            universal_folders = [
                r"%USERPROFILE%\Documents",
                r"%USERPROFILE%\Desktop",
                r"%USERPROFILE%\Downloads",
                r"%USERPROFILE%\Pictures"
            ]
            for u in universal_folders:
                db.add(BackupPolicyPath(policy_id=pol1.id, path_type="universal", path_value=u, is_excluded=False))

            # Excluded paths
            exclusions = [r"%TEMP%", r"%LOCALAPPDATA%\Temp", r"*.tmp", r"*.log"]
            for ex in exclusions:
                db.add(BackupPolicyPath(policy_id=pol1.id, path_type="universal", path_value=ex, is_excluded=True))

            db.commit()

        # 4. Seed Audit Logs
        if db.query(AuditLog).count() == 0:
            print("[+] Seeding system audit log...")
            now = datetime.datetime.now(datetime.timezone.utc)
            logs = [
                AuditLog(action="SYSTEM_INITIALIZED", resource_type="system", details="RetroVault Backup Control Plane daemon started", created_at=now - datetime.timedelta(hours=1)),
                AuditLog(action="POLICY_APPLIED", resource_type="policy", resource_id="1", details="Applied policy 'Windows User Data' to control plane", created_at=now - datetime.timedelta(minutes=30)),
            ]
            db.add_all(logs)
            db.commit()

        print("[SUCCESS] Database seeding completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()

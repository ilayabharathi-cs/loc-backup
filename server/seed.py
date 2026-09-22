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

        # 2. Seed Storage Repositories
        if db.query(StorageRepository).count() == 0:
            print("[+] Seeding primary storage repository...")
            tb_bytes = 1024 ** 4
            repo = StorageRepository(
                name="Primary-Backup-Repository-D",
                repository_type="local",
                path=r"D:\BackupRepository",
                total_bytes=int(10.0 * tb_bytes),
                used_bytes=int(2.4 * tb_bytes),
                available_bytes=int(7.6 * tb_bytes),
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

        # 4. Seed 20 Realistic Windows Clients
        if db.query(Client).count() == 0:
            print("[+] Seeding 20 enterprise Windows workstations (PC-001 through PC-020)...")
            users_list = [
                ("PC-001", "OFFICE-PC-01", "Arun Kumar", "Windows 11 Pro 23H2", "192.168.1.101", "active"),
                ("PC-002", "OFFICE-PC-02", "Sarah Jenkins", "Windows 11 Enterprise", "192.168.1.102", "active"),
                ("PC-003", "OFFICE-PC-03", "David Chen", "Windows 10 Pro 22H2", "192.168.1.103", "offline"),
                ("PC-004", "FINANCE-WS-01", "Elena Rostova", "Windows 11 Enterprise", "192.168.1.104", "active"),
                ("PC-005", "DEV-RIG-01", "Marcus Vance", "Windows 11 Pro 23H2", "192.168.1.105", "active"),
                ("PC-006", "EXEC-LAPTOP-01", "Chloe Bennett", "Windows 11 Pro 23H2", "192.168.1.106", "active"),
                ("PC-007", "DESIGN-MAC-PC", "Alex Rivera", "Windows 11 Pro 23H2", "192.168.1.107", "active"),
                ("PC-008", "HR-TERMINAL-01", "Priya Sharma", "Windows 10 Enterprise", "192.168.1.108", "active"),
                ("PC-009", "SALES-OPS-01", "Thomas Wright", "Windows 11 Pro 22H2", "192.168.1.109", "active"),
                ("PC-010", "LEGAL-STATION-01", "Diana Ross", "Windows 11 Enterprise", "192.168.1.110", "active"),
                ("PC-011", "DEV-RIG-02", "Kenji Sato", "Windows 11 Pro 23H2", "192.168.1.111", "active"),
                ("PC-012", "SUPPORT-PC-01", "Rachel Green", "Windows 10 Pro 22H2", "192.168.1.112", "active"),
                ("PC-013", "QA-LAB-HOST-01", "Victor Vance", "Windows 11 Enterprise", "192.168.1.113", "active"),
                ("PC-014", "RECEPTION-PC-01", "Mary Watson", "Windows 10 Pro 22H2", "192.168.1.114", "active"),
                ("PC-015", "ANALYTICS-SRV-01", "Vikram Singh", "Windows Server 2022", "192.168.1.115", "active"),
                ("PC-016", "MARKETING-MAC-01", "Jessica Alba", "Windows 11 Pro 23H2", "192.168.1.116", "active"),
                ("PC-017", "WAREHOUSE-PC-01", "Bill Goldberg", "Windows 10 Enterprise LTSC", "192.168.1.117", "offline"),
                ("PC-018", "AUDIT-WS-01", "Nathan Drake", "Windows 11 Pro 23H2", "192.168.1.118", "active"),
                ("PC-019", "FIELD-ENGINEER-01", "Samuel Fisher", "Windows 11 Pro 23H2", "192.168.1.119", "active"),
                ("PC-020", "ARCHIVE-DISPATCH-01", "George Costanza", "Windows 10 Pro 22H2", "192.168.1.120", "active"),
            ]

            now = datetime.datetime.now(datetime.timezone.utc)
            clients_db = []
            for cid, hname, user, os_name, ip, stat in users_list:
                c = Client(
                    client_id=cid,
                    hostname=hname,
                    device_id=f"DEV-UUID-{cid}-95",
                    os=os_name,
                    os_version="10.0.22631",
                    ip_address=ip,
                    agent_version="1.4.2",
                    status=stat,
                    last_seen=now if stat == "active" else now - datetime.timedelta(hours=4)
                )
                db.add(c)
                clients_db.append(c)
            db.commit()

            # 5. Seed Jobs & Recovery Points for Clients
            print("[+] Seeding backup jobs and recovery points...")
            pol = db.query(BackupPolicy).first()
            c1 = db.query(Client).filter(Client.client_id == "PC-001").first()
            if c1 and pol:
                j1 = BackupJob(
                    job_id="JOB-9400",
                    client_id=c1.id,
                    policy_id=pol.id,
                    status="completed",
                    started_at=now - datetime.timedelta(minutes=10),
                    completed_at=now - datetime.timedelta(minutes=8)
                )
                db.add(j1)
                db.flush()

                r1 = BackupRun(
                    job_id=j1.id,
                    client_id=c1.id,
                    backup_type="incremental",
                    started_at=j1.started_at,
                    completed_at=j1.completed_at,
                    status="completed",
                    files_processed=42,
                    bytes_processed=412 * 1024 * 1024,
                    bytes_uploaded=412 * 1024 * 1024
                )
                db.add(r1)
                db.flush()

                rp1 = RecoveryPoint(
                    client_id=c1.id,
                    backup_run_id=r1.id,
                    timestamp=j1.completed_at,
                    files_count=42,
                    total_size_bytes=412 * 1024 * 1024,
                    status="valid"
                )
                db.add(rp1)

            c2 = db.query(Client).filter(Client.client_id == "PC-002").first()
            if c2 and pol:
                j2 = BackupJob(
                    job_id="JOB-9399",
                    client_id=c2.id,
                    policy_id=pol.id,
                    status="completed",
                    started_at=now - datetime.timedelta(minutes=15),
                    completed_at=now - datetime.timedelta(minutes=12)
                )
                db.add(j2)
                db.flush()

                r2 = BackupRun(
                    job_id=j2.id,
                    client_id=c2.id,
                    backup_type="incremental",
                    started_at=j2.started_at,
                    completed_at=j2.completed_at,
                    status="completed",
                    files_processed=55,
                    bytes_processed=618 * 1024 * 1024,
                    bytes_uploaded=618 * 1024 * 1024
                )
                db.add(r2)
                db.flush()

                rp2 = RecoveryPoint(
                    client_id=c2.id,
                    backup_run_id=r2.id,
                    timestamp=j2.completed_at,
                    files_count=55,
                    total_size_bytes=618 * 1024 * 1024,
                    status="valid"
                )
                db.add(rp2)

            db.commit()

        # 6. Seed Audit Logs
        if db.query(AuditLog).count() == 0:
            print("[+] Seeding enterprise audit logs...")
            now = datetime.datetime.now(datetime.timezone.utc)
            logs = [
                AuditLog(action="SYSTEM_INITIALIZED", resource_type="system", details="RetroVault Backup Control Plane daemon started", created_at=now - datetime.timedelta(hours=5)),
                AuditLog(action="POLICY_APPLIED", resource_type="policy", resource_id="1", details="Applied policy 'Windows User Data' to enrolled workstations", created_at=now - datetime.timedelta(hours=4)),
                AuditLog(action="BACKUP_COMPLETED", resource_type="job", resource_id="JOB-9400", details="Incremental backup completed for PC-001 (412 MB)", created_at=now - datetime.timedelta(minutes=8)),
                AuditLog(action="BACKUP_COMPLETED", resource_type="job", resource_id="JOB-9399", details="Incremental backup completed for PC-002 (618 MB)", created_at=now - datetime.timedelta(minutes=12)),
                AuditLog(action="CLIENT_TIMEOUT_WARNING", resource_type="client", resource_id="PC-003", details="Heartbeat missed 3 cycles, client marked offline", created_at=now - datetime.timedelta(minutes=20)),
            ]
            db.add_all(logs)
            db.commit()

        print("[SUCCESS] Database seeding completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()

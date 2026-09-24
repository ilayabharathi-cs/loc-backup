"""Database migration helper for V7 Enterprise Operations, Offsite Replication & Security."""

import os
import sqlite3
import json


def run_migration():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "backup.db"),
        os.path.join(os.path.dirname(base_dir), "backup.db"),
    ]

    for db_path in candidates:
        if not os.path.exists(db_path):
            continue
        print(f"Migrating database for V7 Enterprise Operations: {db_path}")
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # 1. Update storage_repositories table
        cols_sr = [c[1] for c in cur.execute("PRAGMA table_info(storage_repositories)")]
        if "endpoint" not in cols_sr:
            cur.execute("ALTER TABLE storage_repositories ADD COLUMN endpoint VARCHAR(500)")
        if "root_path" not in cols_sr:
            cur.execute("ALTER TABLE storage_repositories ADD COLUMN root_path VARCHAR(500)")
        if "protection_mode" not in cols_sr:
            cur.execute("ALTER TABLE storage_repositories ADD COLUMN protection_mode VARCHAR(20) DEFAULT 'NORMAL' NOT NULL")
        if "encryption_enabled" not in cols_sr:
            cur.execute("ALTER TABLE storage_repositories ADD COLUMN encryption_enabled BOOLEAN DEFAULT 0 NOT NULL")
        if "last_health_check" not in cols_sr:
            cur.execute("ALTER TABLE storage_repositories ADD COLUMN last_health_check DATETIME")
        if "configuration" not in cols_sr:
            cur.execute("ALTER TABLE storage_repositories ADD COLUMN configuration TEXT")

        # 2. Create replication_jobs table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS replication_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id VARCHAR(50) UNIQUE NOT NULL,
                source_repository_id INTEGER NOT NULL REFERENCES storage_repositories(id) ON DELETE CASCADE,
                destination_repository_id INTEGER NOT NULL REFERENCES storage_repositories(id) ON DELETE CASCADE,
                recovery_point_id INTEGER REFERENCES recovery_points(id) ON DELETE SET NULL,
                status VARCHAR(30) DEFAULT 'CREATED' NOT NULL,
                total_objects INTEGER DEFAULT 0 NOT NULL,
                completed_objects INTEGER DEFAULT 0 NOT NULL,
                failed_objects INTEGER DEFAULT 0 NOT NULL,
                skipped_objects INTEGER DEFAULT 0 NOT NULL,
                total_bytes BIGINT DEFAULT 0 NOT NULL,
                transferred_bytes BIGINT DEFAULT 0 NOT NULL,
                bandwidth_limit_mbps FLOAT,
                progress_percent FLOAT DEFAULT 0.0 NOT NULL,
                started_at DATETIME,
                completed_at DATETIME,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_replication_jobs_job_id ON replication_jobs (job_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_replication_jobs_status ON replication_jobs (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_replication_jobs_source_repo ON replication_jobs (source_repository_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_replication_jobs_dest_repo ON replication_jobs (destination_repository_id)")

        # 3. Create replication_items table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS replication_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL REFERENCES replication_jobs(id) ON DELETE CASCADE,
                storage_object_id INTEGER REFERENCES storage_objects(id) ON DELETE SET NULL,
                source_path VARCHAR(1000) NOT NULL,
                destination_path VARCHAR(1000) NOT NULL,
                stored_sha256 VARCHAR(64) NOT NULL,
                content_sha256 VARCHAR(64) NOT NULL,
                stored_size BIGINT NOT NULL,
                status VARCHAR(30) DEFAULT 'PENDING' NOT NULL,
                retry_count INTEGER DEFAULT 0 NOT NULL,
                error_message TEXT,
                transferred_at DATETIME
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_replication_items_job_id ON replication_items (job_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_replication_items_status ON replication_items (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_replication_items_content_sha ON replication_items (content_sha256)")

        # 4. Create replication_checkpoints table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS replication_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL REFERENCES replication_jobs(id) ON DELETE CASCADE,
                last_completed_item_id INTEGER,
                completed_objects INTEGER DEFAULT 0 NOT NULL,
                transferred_bytes BIGINT DEFAULT 0 NOT NULL,
                checkpoint_state VARCHAR(50) DEFAULT 'ACTIVE' NOT NULL,
                recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_replication_checkpoints_job_id ON replication_checkpoints (job_id)")

        # 5. Create alert_rules table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) UNIQUE NOT NULL,
                rule_type VARCHAR(50) NOT NULL,
                severity VARCHAR(20) DEFAULT 'WARNING' NOT NULL,
                threshold_value VARCHAR(100),
                is_enabled BOOLEAN DEFAULT 1 NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_alert_rules_rule_type ON alert_rules (rule_type)")

        # 6. Create alerts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER REFERENCES alert_rules(id) ON DELETE SET NULL,
                alert_type VARCHAR(50) NOT NULL,
                severity VARCHAR(20) DEFAULT 'WARNING' NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL,
                resource_type VARCHAR(50),
                resource_id VARCHAR(100),
                acknowledged_by VARCHAR(100),
                acknowledged_at DATETIME,
                resolved_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_alerts_status ON alerts (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_alerts_severity ON alerts (severity)")

        # 7. Create notification_channels table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notification_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) UNIQUE NOT NULL,
                channel_type VARCHAR(30) NOT NULL,
                target VARCHAR(500) NOT NULL,
                is_enabled BOOLEAN DEFAULT 1 NOT NULL,
                configuration TEXT,
                cooldown_seconds INTEGER DEFAULT 300 NOT NULL,
                last_sent_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)

        # 8. Create notification_deliveries table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notification_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL REFERENCES notification_channels(id) ON DELETE CASCADE,
                alert_id INTEGER REFERENCES alerts(id) ON DELETE SET NULL,
                status VARCHAR(20) DEFAULT 'SENT' NOT NULL,
                payload TEXT NOT NULL,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0 NOT NULL,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)

        # 9. Create agent_credentials table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                token_hash VARCHAR(128) NOT NULL,
                status VARCHAR(30) DEFAULT 'ACTIVE' NOT NULL,
                issued_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                confirmed_at DATETIME,
                revoked_at DATETIME,
                expires_at DATETIME,
                rotation_reason VARCHAR(255)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_agent_credentials_client_id ON agent_credentials (client_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_agent_credentials_token_hash ON agent_credentials (token_hash)")

        # 10. Create mfa_settings table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mfa_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                secret_encrypted VARCHAR(500) NOT NULL,
                recovery_codes_hash TEXT NOT NULL,
                is_enabled BOOLEAN DEFAULT 0 NOT NULL,
                enrolled_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                last_verified_at DATETIME
            )
        """)

        # 11. Create system_settings table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category VARCHAR(50) NOT NULL,
                key VARCHAR(100) UNIQUE NOT NULL,
                value TEXT NOT NULL,
                description TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_by VARCHAR(100)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_system_settings_category ON system_settings (category)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_system_settings_key ON system_settings (key)")

        # 12. Create dr_tests table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dr_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id VARCHAR(50) UNIQUE NOT NULL,
                recovery_point_id INTEGER NOT NULL REFERENCES recovery_points(id) ON DELETE CASCADE,
                target_path VARCHAR(1000) NOT NULL,
                files_tested INTEGER DEFAULT 0 NOT NULL,
                bytes_tested BIGINT DEFAULT 0 NOT NULL,
                files_verified INTEGER DEFAULT 0 NOT NULL,
                failures INTEGER DEFAULT 0 NOT NULL,
                duration_seconds FLOAT DEFAULT 0.0 NOT NULL,
                result VARCHAR(30) DEFAULT 'PASSED' NOT NULL,
                error_message TEXT,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                completed_at DATETIME
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_dr_tests_test_id ON dr_tests (test_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_dr_tests_result ON dr_tests (result)")

        # 13. Seed default alert rules if empty
        existing_rules = cur.execute("SELECT COUNT(*) FROM alert_rules").fetchone()[0]
        if existing_rules == 0:
            default_rules = [
                ("Backup Failure Alert", "BACKUP_FAILED", "ERROR", None, "Triggers when a backup run encounters fatal errors"),
                ("RPO Target Breach", "RPO_BREACH", "WARNING", "120", "Triggers when backup age exceeds configured RPO target seconds"),
                ("Low Repository Storage", "LOW_STORAGE", "WARNING", "15", "Triggers when available repository capacity falls below threshold percent"),
                ("Agent Offline Detector", "AGENT_OFFLINE", "WARNING", "300", "Triggers when an active agent misses heartbeats beyond threshold"),
                ("Replication Failure", "REPLICATION_FAILED", "ERROR", None, "Triggers when repository replication fails to verify objects"),
                ("Storage Object Bit-Rot", "CORRUPTED_OBJECT", "CRITICAL", None, "Triggers when scrubbing discovers a corrupted CAS object"),
                ("Security Anomaly", "SECURITY_EVENT", "WARNING", None, "Triggers on unauthorized cross-client restore or failed admin logins")
            ]
            for r in default_rules:
                cur.execute("""
                    INSERT INTO alert_rules (name, rule_type, severity, threshold_value, description)
                    VALUES (?, ?, ?, ?, ?)
                """, r)

        # 14. Seed default system settings if empty
        existing_settings = cur.execute("SELECT COUNT(*) FROM system_settings").fetchone()[0]
        if existing_settings == 0:
            defaults = [
                ("general", "site_name", "RetroVault Enterprise Control Server", "Display name of backup server"),
                ("server", "listen_port", "8000", "Control plane API port"),
                ("repositories", "default_retention_days", "30", "Default fallback retention period"),
                ("security", "mfa_enforced", "false", "Enforce MFA for all admin accounts"),
                ("security", "session_timeout_minutes", "60", "Admin UI session idle timeout"),
                ("agents", "heartbeat_timeout_seconds", "60", "Threshold before marking agent offline"),
                ("backup", "default_compression", "zstd", "Default algorithm: zstd or gzip"),
                ("retention", "gfs_evaluation_hour", "2", "Hour of day (UTC) to run daily retention sweep"),
                ("replication", "default_bandwidth_limit_mbps", "50", "Bandwidth throttling limit for offsite transfers"),
                ("notifications", "email_enabled", "false", "Global toggle for email alert delivery"),
                ("dr", "auto_dr_test_interval_days", "7", "Frequency of non-destructive sandbox restore drills")
            ]
            for s in defaults:
                cur.execute("""
                    INSERT INTO system_settings (category, key, value, description)
                    VALUES (?, ?, ?, ?)
                """, s)

        con.commit()
        con.close()
        print(f"V7 migration successfully applied to: {db_path}")


if __name__ == "__main__":
    run_migration()

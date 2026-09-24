"""Database migration helper for V8 Ransomware Resilience, Advanced Security & Enterprise Scale."""

import os
import sqlite3


def run_migration():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "backup.db"),
        os.path.join(os.path.dirname(base_dir), "backup.db"),
    ]

    for db_path in candidates:
        if not os.path.exists(db_path):
            continue
        print(f"Migrating database for V8 Security Resilience: {db_path}")
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # 1. Update clients table
        cols_c = [c[1] for c in cur.execute("PRAGMA table_info(clients)")]
        if "group_id" not in cols_c:
            cur.execute("ALTER TABLE clients ADD COLUMN group_id INTEGER REFERENCES client_groups(id) ON DELETE SET NULL")
        if "policy_override_id" not in cols_c:
            cur.execute("ALTER TABLE clients ADD COLUMN policy_override_id INTEGER REFERENCES backup_policies(id) ON DELETE SET NULL")
        if "effective_policy_version" not in cols_c:
            cur.execute("ALTER TABLE clients ADD COLUMN effective_policy_version INTEGER")

        # 2. Update recovery_points table
        cols_rp = [c[1] for c in cur.execute("PRAGMA table_info(recovery_points)")]
        if "protection_state" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN protection_state VARCHAR(30) DEFAULT 'NORMAL' NOT NULL")
        if "security_hold_until" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN security_hold_until DATETIME")
        if "protected_reason" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN protected_reason VARCHAR(255)")
        if "protected_by" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN protected_by VARCHAR(100)")
        if "protection_created_at" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN protection_created_at DATETIME")

        # 3. Update storage_repositories table
        cols_sr = [c[1] for c in cur.execute("PRAGMA table_info(storage_repositories)")]
        if "immutability_state" not in cols_sr:
            cur.execute("ALTER TABLE storage_repositories ADD COLUMN immutability_state VARCHAR(30) DEFAULT 'DISABLED' NOT NULL")
        if "capabilities_json" not in cols_sr:
            cur.execute("ALTER TABLE storage_repositories ADD COLUMN capabilities_json TEXT")

        # 4. Update storage_objects table
        cols_so = [c[1] for c in cur.execute("PRAGMA table_info(storage_objects)")]
        if "quarantined_at" not in cols_so:
            cur.execute("ALTER TABLE storage_objects ADD COLUMN quarantined_at DATETIME")
        if "quarantine_reason" not in cols_so:
            cur.execute("ALTER TABLE storage_objects ADD COLUMN quarantine_reason VARCHAR(255)")

        # 5. Create security_profiles table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS security_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) UNIQUE NOT NULL,
                description VARCHAR(255),
                anomaly_threshold INTEGER DEFAULT 60 NOT NULL,
                max_deletion_count INTEGER DEFAULT 5 NOT NULL,
                max_deletion_pct FLOAT DEFAULT 10.0 NOT NULL,
                require_mfa_for_deletion BOOLEAN DEFAULT 1 NOT NULL,
                entropy_threshold FLOAT DEFAULT 7.2 NOT NULL,
                is_default BOOLEAN DEFAULT 0 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)

        # 6. Create client_groups table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS client_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) UNIQUE NOT NULL,
                description VARCHAR(255),
                policy_id INTEGER REFERENCES backup_policies(id) ON DELETE SET NULL,
                security_profile_id INTEGER REFERENCES security_profiles(id) ON DELETE SET NULL,
                repository_id INTEGER REFERENCES storage_repositories(id) ON DELETE SET NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_client_groups_name ON client_groups (name)")

        # 7. Create policy_versions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS policy_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL REFERENCES backup_policies(id) ON DELETE CASCADE,
                version INTEGER NOT NULL,
                definition_json TEXT NOT NULL,
                change_summary VARCHAR(255),
                created_by VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_policy_versions_policy_id ON policy_versions (policy_id)")

        # 8. Create security_events table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type VARCHAR(60) NOT NULL,
                severity VARCHAR(20) DEFAULT 'MEDIUM' NOT NULL,
                client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                repository_id INTEGER REFERENCES storage_repositories(id) ON DELETE SET NULL,
                run_id INTEGER REFERENCES backup_runs(id) ON DELETE SET NULL,
                recovery_point_id INTEGER REFERENCES recovery_points(id) ON DELETE SET NULL,
                score INTEGER DEFAULT 0 NOT NULL,
                description TEXT NOT NULL,
                evidence_json TEXT,
                status VARCHAR(30) DEFAULT 'OPEN' NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                acknowledged_at DATETIME,
                resolved_at DATETIME,
                resolved_by VARCHAR(100)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_security_events_type ON security_events (event_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_security_events_status ON security_events (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_security_events_client_id ON security_events (client_id)")

        # 9. Create security_incidents table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS security_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_number VARCHAR(50) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                severity VARCHAR(20) DEFAULT 'HIGH' NOT NULL,
                status VARCHAR(40) DEFAULT 'DETECTED' NOT NULL,
                client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                candidate_recovery_point_id INTEGER REFERENCES recovery_points(id) ON DELETE SET NULL,
                restore_test_id VARCHAR(50),
                containment_notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                closed_at DATETIME,
                closed_by VARCHAR(100)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_security_incidents_number ON security_incidents (incident_number)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_security_incidents_status ON security_incidents (status)")

        # 10. Create configuration_drifts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS configuration_drifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                drift_type VARCHAR(50) NOT NULL,
                expected_value VARCHAR(255) NOT NULL,
                actual_value VARCHAR(255) NOT NULL,
                severity VARCHAR(20) DEFAULT 'WARNING' NOT NULL,
                status VARCHAR(30) DEFAULT 'DETECTED' NOT NULL,
                detected_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                resolved_at DATETIME
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_configuration_drifts_client_id ON configuration_drifts (client_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_configuration_drifts_status ON configuration_drifts (status)")

        # 11. Create integrity_scans table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS integrity_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id VARCHAR(50) UNIQUE NOT NULL,
                repository_id INTEGER NOT NULL REFERENCES storage_repositories(id) ON DELETE CASCADE,
                scan_type VARCHAR(30) DEFAULT 'FULL' NOT NULL,
                total_objects INTEGER DEFAULT 0 NOT NULL,
                valid_objects INTEGER DEFAULT 0 NOT NULL,
                corrupted_objects INTEGER DEFAULT 0 NOT NULL,
                missing_objects INTEGER DEFAULT 0 NOT NULL,
                duration_seconds FLOAT DEFAULT 0.0 NOT NULL,
                status VARCHAR(30) DEFAULT 'RUNNING' NOT NULL,
                details_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_integrity_scans_scan_id ON integrity_scans (scan_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_integrity_scans_repo_id ON integrity_scans (repository_id)")

        # 12. Create deletion_guards table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS deletion_guards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_type VARCHAR(50) NOT NULL,
                requester_id INTEGER,
                requester_username VARCHAR(100) NOT NULL,
                target_resource_type VARCHAR(50) NOT NULL,
                target_resource_id VARCHAR(100) NOT NULL,
                payload_json TEXT NOT NULL,
                status VARCHAR(30) DEFAULT 'PENDING' NOT NULL,
                risk_score INTEGER DEFAULT 50 NOT NULL,
                approved_by VARCHAR(100),
                approved_at DATETIME,
                expires_at DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_deletion_guards_status ON deletion_guards (status)")

        # 13. Create security_simulations table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS security_simulations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                simulation_id VARCHAR(50) UNIQUE NOT NULL,
                scenario_type VARCHAR(60) NOT NULL,
                status VARCHAR(30) DEFAULT 'PENDING' NOT NULL,
                sandbox_path VARCHAR(500) NOT NULL,
                parameters_json TEXT,
                results_json TEXT,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                completed_at DATETIME
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_security_simulations_sim_id ON security_simulations (simulation_id)")

        # 14. Seed default security profile if none exists
        count_sp = cur.execute("SELECT COUNT(*) FROM security_profiles").fetchone()[0]
        if count_sp == 0:
            cur.execute("""
                INSERT INTO security_profiles (name, description, anomaly_threshold, max_deletion_count, max_deletion_pct, require_mfa_for_deletion, entropy_threshold, is_default)
                VALUES ('Standard Enterprise Security', 'Default baseline ransomware resilience and deletion guard profile', 60, 5, 10.0, 1, 7.2, 1)
            """)

        # 15. Seed default client group if none exists
        count_cg = cur.execute("SELECT COUNT(*) FROM client_groups").fetchone()[0]
        if count_cg == 0:
            cur.execute("""
                INSERT INTO client_groups (name, description)
                VALUES ('Default Fleet', 'Standard corporate fleet machines')
            """)

        con.commit()
        con.close()
        print(f"V8 migration successfully applied to: {db_path}")


if __name__ == "__main__":
    run_migration()

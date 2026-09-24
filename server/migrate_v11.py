"""Database migration runner for RetroVault V11 Application-Aware Data Protection & Automated Recovery."""

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
        print(f"Migrating database for V11 Application-Aware Protection: {db_path}")
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # 1. workloads
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workload_id VARCHAR(100) UNIQUE NOT NULL,
                client_id VARCHAR(100) NOT NULL,
                type VARCHAR(50) NOT NULL,
                name VARCHAR(150) NOT NULL,
                version VARCHAR(50),
                status VARCHAR(50) DEFAULT 'DISCOVERED' NOT NULL,
                health VARCHAR(50) DEFAULT 'HEALTHY' NOT NULL,
                protection_state VARCHAR(50) DEFAULT 'UNPROTECTED' NOT NULL,
                consistency_capability VARCHAR(50) DEFAULT 'UNKNOWN' NOT NULL,
                last_protected_at DATETIME,
                last_verified_at DATETIME,
                config_json TEXT,
                metadata_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workloads_workload_id ON workloads (workload_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workloads_client_id ON workloads (client_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workloads_type ON workloads (type)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workloads_status ON workloads (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workloads_protection_state ON workloads (protection_state)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workloads_created_at ON workloads (created_at)")

        # 2. workload_providers
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workload_providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_type VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                capabilities_json TEXT NOT NULL,
                settings_json TEXT,
                is_enabled BOOLEAN DEFAULT 1 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workload_providers_type ON workload_providers (provider_type)")

        # 3. workload_protections
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workload_protections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workload_id VARCHAR(100) NOT NULL,
                policy_id VARCHAR(100),
                backup_mode VARCHAR(30) DEFAULT 'FULL' NOT NULL,
                schedule_cron VARCHAR(100),
                is_active BOOLEAN DEFAULT 1 NOT NULL,
                settings_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workload_protections_workload_id ON workload_protections (workload_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workload_protections_policy_id ON workload_protections (policy_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workload_protections_is_active ON workload_protections (is_active)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workload_protections_created_at ON workload_protections (created_at)")

        # 4. workload_artifacts
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workload_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_id VARCHAR(100) UNIQUE NOT NULL,
                workload_id VARCHAR(100) NOT NULL,
                recovery_point_id VARCHAR(100) NOT NULL,
                artifact_name VARCHAR(255) NOT NULL,
                artifact_type VARCHAR(50) NOT NULL,
                storage_object_id VARCHAR(100),
                size_bytes BIGINT DEFAULT 0 NOT NULL,
                checksum_sha256 VARCHAR(64) NOT NULL,
                artifact_metadata_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workload_artifacts_artifact_id ON workload_artifacts (artifact_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workload_artifacts_workload_id ON workload_artifacts (workload_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workload_artifacts_recovery_point_id ON workload_artifacts (recovery_point_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_workload_artifacts_created_at ON workload_artifacts (created_at)")

        # 5. application_consistency_records
        cur.execute("""
            CREATE TABLE IF NOT EXISTS application_consistency_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id VARCHAR(100) UNIQUE NOT NULL,
                recovery_point_id VARCHAR(100) NOT NULL,
                workload_id VARCHAR(100) NOT NULL,
                consistency_state VARCHAR(50) NOT NULL,
                verification_method VARCHAR(80) NOT NULL,
                evidence_json TEXT NOT NULL,
                verified_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                verified_by VARCHAR(100) DEFAULT 'SYSTEM' NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_app_consistency_rec_id ON application_consistency_records (record_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_app_consistency_rp_id ON application_consistency_records (recovery_point_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_app_consistency_workload_id ON application_consistency_records (workload_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_app_consistency_state ON application_consistency_records (consistency_state)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_app_consistency_verified_at ON application_consistency_records (verified_at)")

        # 6. backup_chains
        cur.execute("""
            CREATE TABLE IF NOT EXISTS backup_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id VARCHAR(100) UNIQUE NOT NULL,
                workload_id VARCHAR(100) NOT NULL,
                base_recovery_point_id VARCHAR(100) NOT NULL,
                latest_recovery_point_id VARCHAR(100) NOT NULL,
                chain_length INTEGER DEFAULT 1 NOT NULL,
                status VARCHAR(30) DEFAULT 'VALID' NOT NULL,
                broken_reason TEXT,
                last_validated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                metadata_json TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_backup_chains_chain_id ON backup_chains (chain_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_backup_chains_workload_id ON backup_chains (workload_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_backup_chains_status ON backup_chains (status)")

        # 7. recovery_verifications
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recovery_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verification_id VARCHAR(100) UNIQUE NOT NULL,
                recovery_point_id VARCHAR(100) NOT NULL,
                workload_id VARCHAR(100) NOT NULL,
                verification_type VARCHAR(50) NOT NULL,
                sandbox_path VARCHAR(255) NOT NULL,
                status VARCHAR(30) DEFAULT 'PENDING' NOT NULL,
                started_at DATETIME,
                completed_at DATETIME,
                duration_ms REAL DEFAULT 0.0 NOT NULL,
                error_message TEXT,
                evidence_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_rec_verif_id ON recovery_verifications (verification_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_rec_verif_rp_id ON recovery_verifications (recovery_point_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_rec_verif_workload_id ON recovery_verifications (workload_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_rec_verif_status ON recovery_verifications (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_rec_verif_created_at ON recovery_verifications (created_at)")

        # 8. recovery_verification_steps
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recovery_verification_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verification_id VARCHAR(100) NOT NULL,
                step_name VARCHAR(100) NOT NULL,
                step_order INTEGER NOT NULL,
                status VARCHAR(30) DEFAULT 'PENDING' NOT NULL,
                details_json TEXT,
                started_at DATETIME,
                completed_at DATETIME,
                error_message TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_rec_verif_steps_verif_id ON recovery_verification_steps (verification_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_rec_verif_steps_status ON recovery_verification_steps (status)")

        # 9. recovery_readiness_records
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recovery_readiness_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workload_id VARCHAR(100) NOT NULL,
                client_id VARCHAR(100) NOT NULL,
                readiness_state VARCHAR(30) NOT NULL,
                contributing_signals_json TEXT NOT NULL,
                latest_backup_at DATETIME,
                latest_verified_rp_id VARCHAR(100),
                rpo_compliance_percent REAL DEFAULT 100.0 NOT NULL,
                rto_estimate_seconds REAL,
                evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_rec_readiness_workload_id ON recovery_readiness_records (workload_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_rec_readiness_client_id ON recovery_readiness_records (client_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_rec_readiness_state ON recovery_readiness_records (readiness_state)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_rec_readiness_evaluated_at ON recovery_readiness_records (evaluated_at)")

        # 10. policy_lifecycles
        cur.execute("""
            CREATE TABLE IF NOT EXISTS policy_lifecycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id VARCHAR(100) NOT NULL,
                version INTEGER DEFAULT 1 NOT NULL,
                lifecycle_state VARCHAR(30) DEFAULT 'DRAFT' NOT NULL,
                definition_json TEXT NOT NULL,
                effective_at DATETIME,
                created_by VARCHAR(100) DEFAULT 'SYSTEM' NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_policy_lifecycles_policy_id ON policy_lifecycles (policy_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_policy_lifecycles_state ON policy_lifecycles (lifecycle_state)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_policy_lifecycles_created_at ON policy_lifecycles (created_at)")

        # 11. policy_approvals
        cur.execute("""
            CREATE TABLE IF NOT EXISTS policy_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_lifecycle_id INTEGER NOT NULL,
                requested_by VARCHAR(100) NOT NULL,
                approved_by VARCHAR(100),
                status VARCHAR(30) DEFAULT 'PENDING' NOT NULL,
                approval_notes TEXT,
                approved_at DATETIME
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_policy_approvals_lifecycle_id ON policy_approvals (policy_lifecycle_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_policy_approvals_status ON policy_approvals (status)")

        # 12. remediation_actions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS remediation_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                remediation_id VARCHAR(100) UNIQUE NOT NULL,
                action_type VARCHAR(60) NOT NULL,
                target_resource_type VARCHAR(50) NOT NULL,
                target_resource_id VARCHAR(150) NOT NULL,
                requires_dual_approval BOOLEAN DEFAULT 0 NOT NULL,
                first_approver VARCHAR(100),
                second_approver VARCHAR(100),
                status VARCHAR(30) DEFAULT 'PENDING_APPROVAL' NOT NULL,
                execution_result_json TEXT,
                audit_event_id VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                executed_at DATETIME
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_remediation_rem_id ON remediation_actions (remediation_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_remediation_type ON remediation_actions (action_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_remediation_target_id ON remediation_actions (target_resource_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_remediation_status ON remediation_actions (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_remediation_created_at ON remediation_actions (created_at)")

        # 13. dependency_relations
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dependency_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_type VARCHAR(50) NOT NULL,
                parent_id VARCHAR(150) NOT NULL,
                child_type VARCHAR(50) NOT NULL,
                child_id VARCHAR(150) NOT NULL,
                relation_type VARCHAR(50) DEFAULT 'REQUIRES' NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_dep_rel_parent ON dependency_relations (parent_type, parent_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_dep_rel_child ON dependency_relations (child_type, child_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_dep_rel_created_at ON dependency_relations (created_at)")

        con.commit()
        con.close()
        print(f"V11 migration applied successfully to {db_path}")


if __name__ == "__main__":
    run_migration()

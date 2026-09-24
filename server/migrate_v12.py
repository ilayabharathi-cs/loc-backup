"""Database migration runner for RetroVault V12 Cloud & Hybrid Storage Tiering."""

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
        print(f"Migrating database for V12 Cloud & Hybrid Storage Tiering: {db_path}")
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # 1. cloud_credentials
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cloud_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credential_id VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(150) UNIQUE NOT NULL,
                provider VARCHAR(50) DEFAULT 's3' NOT NULL,
                endpoint VARCHAR(500),
                region VARCHAR(50) DEFAULT 'us-east-1',
                access_key_encrypted TEXT NOT NULL,
                secret_key_encrypted TEXT NOT NULL,
                prefix VARCHAR(255),
                use_tls BOOLEAN DEFAULT 1 NOT NULL,
                verify_ssl BOOLEAN DEFAULT 1 NOT NULL,
                status VARCHAR(50) DEFAULT 'configured' NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cloud_credentials_credential_id ON cloud_credentials (credential_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cloud_credentials_name ON cloud_credentials (name)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cloud_credentials_provider ON cloud_credentials (provider)")

        # 2. storage_tiers
        cur.execute("""
            CREATE TABLE IF NOT EXISTS storage_tiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tier_id VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(150) UNIQUE NOT NULL,
                tier_type VARCHAR(50) DEFAULT 'CLOUD_S3' NOT NULL,
                provider VARCHAR(50) DEFAULT 's3' NOT NULL,
                credential_id INTEGER REFERENCES cloud_credentials(id) ON DELETE SET NULL,
                bucket VARCHAR(255) NOT NULL,
                prefix VARCHAR(255) DEFAULT '',
                state VARCHAR(50) DEFAULT 'CREATED' NOT NULL,
                object_lock_enabled BOOLEAN DEFAULT 0 NOT NULL,
                retention_period_days INTEGER DEFAULT 0 NOT NULL,
                immutability_mode VARCHAR(50) DEFAULT 'NONE' NOT NULL,
                is_default BOOLEAN DEFAULT 0 NOT NULL,
                is_enabled BOOLEAN DEFAULT 1 NOT NULL,
                config_json TEXT,
                last_validated_at DATETIME,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_storage_tiers_tier_id ON storage_tiers (tier_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_storage_tiers_name ON storage_tiers (name)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_storage_tiers_state ON storage_tiers (state)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_storage_tiers_credential_id ON storage_tiers (credential_id)")

        # 3. cloud_offloaded_objects
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cloud_offloaded_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                offload_id VARCHAR(100) UNIQUE NOT NULL,
                storage_tier_id INTEGER NOT NULL REFERENCES storage_tiers(id) ON DELETE CASCADE,
                storage_object_id VARCHAR(64) NOT NULL REFERENCES storage_objects(object_id) ON DELETE RESTRICT,
                remote_key VARCHAR(500) NOT NULL,
                remote_sha256 VARCHAR(64) NOT NULL,
                remote_size BIGINT NOT NULL,
                state VARCHAR(50) DEFAULT 'OFFLOADED' NOT NULL,
                verification_status VARCHAR(50) DEFAULT 'PENDING' NOT NULL,
                verified_at DATETIME,
                offloaded_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                offloaded_by VARCHAR(100),
                etag VARCHAR(100),
                object_lock_until DATETIME,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cloud_offloaded_objects_offload_id ON cloud_offloaded_objects (offload_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cloud_offloaded_objects_storage_tier_id ON cloud_offloaded_objects (storage_tier_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cloud_offloaded_objects_storage_object_id ON cloud_offloaded_objects (storage_object_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cloud_offloaded_objects_remote_sha256 ON cloud_offloaded_objects (remote_sha256)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cloud_offloaded_objects_state ON cloud_offloaded_objects (state)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cloud_offload_tier_obj ON cloud_offloaded_objects (storage_tier_id, storage_object_id)")

        # 4. virtual_recovery_sessions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS virtual_recovery_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id VARCHAR(100) UNIQUE NOT NULL,
                recovery_point_id INTEGER NOT NULL REFERENCES recovery_points(id) ON DELETE RESTRICT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
                workload_id VARCHAR(100),
                target_path VARCHAR(1000) NOT NULL,
                mount_point VARCHAR(1000),
                provider_type VARCHAR(50) DEFAULT 'LOCAL_VIRTUAL' NOT NULL,
                cloud_tier_id INTEGER REFERENCES storage_tiers(id) ON DELETE SET NULL,
                state VARCHAR(50) DEFAULT 'CREATED' NOT NULL,
                hydration_status VARCHAR(50) DEFAULT 'NOT_STARTED' NOT NULL,
                total_files INTEGER DEFAULT 0 NOT NULL,
                total_bytes BIGINT DEFAULT 0 NOT NULL,
                hydrated_bytes BIGINT DEFAULT 0 NOT NULL,
                hydrated_files INTEGER DEFAULT 0 NOT NULL,
                hydration_speed_bps REAL DEFAULT 0.0 NOT NULL,
                hydration_eta_seconds REAL,
                read_requests_count INTEGER DEFAULT 0 NOT NULL,
                bytes_read BIGINT DEFAULT 0 NOT NULL,
                cache_hits INTEGER DEFAULT 0 NOT NULL,
                cache_misses INTEGER DEFAULT 0 NOT NULL,
                cache_bytes BIGINT DEFAULT 0 NOT NULL,
                time_to_first_access_ms REAL,
                time_to_app_ready_ms REAL,
                time_to_full_hydration_ms REAL,
                error_message TEXT,
                error_details_json TEXT,
                session_metadata_json TEXT,
                created_by VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                prepared_at DATETIME,
                mounted_at DATETIME,
                first_access_at DATETIME,
                app_ready_at DATETIME,
                hydration_started_at DATETIME,
                completed_at DATETIME,
                unmounted_at DATETIME,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_virtual_recovery_sessions_session_id ON virtual_recovery_sessions (session_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_virtual_recovery_sessions_recovery_point_id ON virtual_recovery_sessions (recovery_point_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_virtual_recovery_sessions_client_id ON virtual_recovery_sessions (client_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_virtual_recovery_sessions_state ON virtual_recovery_sessions (state)")

        # 5. virtual_recovery_hydration_items
        cur.execute("""
            CREATE TABLE IF NOT EXISTS virtual_recovery_hydration_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES virtual_recovery_sessions(id) ON DELETE CASCADE,
                relative_path VARCHAR(1000) NOT NULL,
                storage_object_id VARCHAR(64),
                size_bytes BIGINT DEFAULT 0 NOT NULL,
                sha256 VARCHAR(64) NOT NULL,
                status VARCHAR(30) DEFAULT 'PENDING' NOT NULL,
                fetch_source VARCHAR(30),
                hydrated_at DATETIME,
                error_message TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_virtual_recovery_hydration_items_session_id ON virtual_recovery_hydration_items (session_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_vrec_item_session_path ON virtual_recovery_hydration_items (session_id, relative_path)")

        con.commit()
        con.close()
        print(f"Migration completed for {db_path}")



if __name__ == "__main__":
    run_migration()

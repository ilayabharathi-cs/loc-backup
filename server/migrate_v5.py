"""Database migration helper for V5 Storage Optimization, GFS Retention, and GC schema."""

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
        print(f"Migrating database: {db_path}")
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # Drop previous partial V5 tables if any
        cur.execute("DROP TABLE IF EXISTS garbage_collection_items")
        cur.execute("DROP TABLE IF EXISTS garbage_collection_jobs")
        cur.execute("DROP TABLE IF EXISTS retention_evaluations")
        cur.execute("DROP TABLE IF EXISTS retention_policies")
        cur.execute("DROP TABLE IF EXISTS storage_objects")

        # 1. Create storage_objects table
        cur.execute("""
            CREATE TABLE storage_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id VARCHAR(64) UNIQUE NOT NULL,
                content_sha256 VARCHAR(64) NOT NULL,
                stored_sha256 VARCHAR(64) NOT NULL,
                original_size BIGINT NOT NULL,
                stored_size BIGINT NOT NULL,
                compression_algorithm VARCHAR(20) DEFAULT 'NONE' NOT NULL,
                compression_ratio FLOAT DEFAULT 1.0 NOT NULL,
                encryption_status VARCHAR(20) DEFAULT 'NONE' NOT NULL,
                storage_path VARCHAR(500) NOT NULL,
                reference_count INTEGER DEFAULT 1 NOT NULL,
                state VARCHAR(20) DEFAULT 'AVAILABLE' NOT NULL,
                integrity_status VARCHAR(20) DEFAULT 'VALID' NOT NULL,
                verified_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_storage_objects_id ON storage_objects (id)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_storage_objects_object_id ON storage_objects (object_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_storage_objects_content_sha256 ON storage_objects (content_sha256)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_storage_objects_stored_sha256 ON storage_objects (stored_sha256)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_storage_objects_state ON storage_objects (state)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_storage_objects_reference_count ON storage_objects (reference_count)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_storage_obj_content_sha ON storage_objects (content_sha256)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_storage_obj_state_ref ON storage_objects (state, reference_count)")

        # 2. Create retention_policies table
        cur.execute("""
            CREATE TABLE retention_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER UNIQUE REFERENCES backup_policies(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                keep_last INTEGER DEFAULT 10 NOT NULL,
                daily INTEGER DEFAULT 7 NOT NULL,
                weekly INTEGER DEFAULT 4 NOT NULL,
                monthly INTEGER DEFAULT 12 NOT NULL,
                yearly INTEGER DEFAULT 7 NOT NULL,
                timezone VARCHAR(50) DEFAULT 'UTC' NOT NULL,
                is_active BOOLEAN DEFAULT 1 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_retention_policies_id ON retention_policies (id)")

        # 3. Create retention_evaluations table
        cur.execute("""
            CREATE TABLE retention_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                retention_policy_id INTEGER REFERENCES retention_policies(id) ON DELETE SET NULL,
                evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                total_recovery_points INTEGER DEFAULT 0 NOT NULL,
                protected_count INTEGER DEFAULT 0 NOT NULL,
                expired_count INTEGER DEFAULT 0 NOT NULL,
                reclaimed_bytes BIGINT DEFAULT 0 NOT NULL,
                details TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_retention_evaluations_id ON retention_evaluations (id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_retention_evaluations_retention_policy_id ON retention_evaluations (retention_policy_id)")

        # 4. Create garbage_collection_jobs table
        cur.execute("""
            CREATE TABLE garbage_collection_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id VARCHAR(50) UNIQUE NOT NULL,
                status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                candidates_found INTEGER DEFAULT 0 NOT NULL,
                objects_deleted INTEGER DEFAULT 0 NOT NULL,
                objects_skipped INTEGER DEFAULT 0 NOT NULL,
                bytes_reclaimed BIGINT DEFAULT 0 NOT NULL,
                error_message VARCHAR(500),
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_garbage_collection_jobs_id ON garbage_collection_jobs (id)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_garbage_collection_jobs_job_id ON garbage_collection_jobs (job_id)")

        # 5. Create garbage_collection_items table
        cur.execute("""
            CREATE TABLE garbage_collection_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gc_job_id INTEGER NOT NULL REFERENCES garbage_collection_jobs(id) ON DELETE CASCADE,
                storage_object_id INTEGER NOT NULL REFERENCES storage_objects(id) ON DELETE CASCADE,
                object_sha256 VARCHAR(64) NOT NULL,
                stored_size BIGINT DEFAULT 0 NOT NULL,
                status VARCHAR(20) DEFAULT 'marked' NOT NULL,
                reason VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_garbage_collection_items_id ON garbage_collection_items (id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_garbage_collection_items_gc_job_id ON garbage_collection_items (gc_job_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_garbage_collection_items_storage_object_id ON garbage_collection_items (storage_object_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gc_item_job_obj ON garbage_collection_items (gc_job_id, storage_object_id)")

        # 6. Update recovery_points table
        cols_rp = [c[1] for c in cur.execute("PRAGMA table_info(recovery_points)")]
        if "retention_status" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN retention_status VARCHAR(20) DEFAULT 'active' NOT NULL")
        if "is_daily" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN is_daily BOOLEAN DEFAULT 0 NOT NULL")
        if "is_weekly" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN is_weekly BOOLEAN DEFAULT 0 NOT NULL")
        if "is_monthly" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN is_monthly BOOLEAN DEFAULT 0 NOT NULL")
        if "is_yearly" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN is_yearly BOOLEAN DEFAULT 0 NOT NULL")
        if "is_manual_protected" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN is_manual_protected BOOLEAN DEFAULT 0 NOT NULL")
        if "expires_at" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN expires_at DATETIME")
        if "retention_tier" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN retention_tier VARCHAR(20)")

        # 7. Update backup_files table
        cols_bf = [c[1] for c in cur.execute("PRAGMA table_info(backup_files)")]
        if "storage_object_id" not in cols_bf:
            cur.execute("ALTER TABLE backup_files ADD COLUMN storage_object_id INTEGER REFERENCES storage_objects(id)")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_backup_files_storage_object_id ON backup_files (storage_object_id)")

        con.commit()
        con.close()
        print(f"Migration completed successfully for {db_path}")


if __name__ == "__main__":
    run_migration()

"""Database migration helper for V6 Restore & Disaster Recovery schema."""

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
        print(f"Migrating database for V6 Restore & Disaster Recovery: {db_path}")
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # 1. Update restore_jobs columns
        cols_rj = [c[1] for c in cur.execute("PRAGMA table_info(restore_jobs)")]
        if "restore_mode" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN restore_mode VARCHAR(30) DEFAULT 'FULL_RECOVERY_POINT' NOT NULL")
        if "conflict_mode" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN conflict_mode VARCHAR(20) DEFAULT 'OVERWRITE' NOT NULL")
        if "metadata_mode" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN metadata_mode VARCHAR(20) DEFAULT 'BASIC' NOT NULL")
        if "total_files" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN total_files INTEGER DEFAULT 0 NOT NULL")
        if "completed_files" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN completed_files INTEGER DEFAULT 0 NOT NULL")
        if "failed_files" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN failed_files INTEGER DEFAULT 0 NOT NULL")
        if "skipped_files" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN skipped_files INTEGER DEFAULT 0 NOT NULL")
        if "total_bytes" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN total_bytes BIGINT DEFAULT 0 NOT NULL")
        if "restored_bytes" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN restored_bytes BIGINT DEFAULT 0 NOT NULL")
        if "verified_bytes" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN verified_bytes BIGINT DEFAULT 0 NOT NULL")
        if "progress_percent" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN progress_percent FLOAT DEFAULT 0.0 NOT NULL")
        if "cancelled_at" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN cancelled_at DATETIME")
        if "restore_requested_at" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN restore_requested_at DATETIME")
        if "first_byte_restored_at" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN first_byte_restored_at DATETIME")
        if "error_message" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN error_message TEXT")
        if "updated_at" not in cols_rj:
            cur.execute("ALTER TABLE restore_jobs ADD COLUMN updated_at DATETIME")

        # 2. Create restore_items table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS restore_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restore_job_id INTEGER NOT NULL REFERENCES restore_jobs(id) ON DELETE CASCADE,
                backup_file_id INTEGER REFERENCES backup_files(id) ON DELETE SET NULL,
                relative_path VARCHAR(1000) NOT NULL,
                destination_path VARCHAR(1000) NOT NULL,
                source_size BIGINT DEFAULT 0 NOT NULL,
                restored_size BIGINT DEFAULT 0 NOT NULL,
                source_sha256 VARCHAR(64),
                restored_sha256 VARCHAR(64),
                status VARCHAR(20) DEFAULT 'PENDING' NOT NULL,
                retry_count INTEGER DEFAULT 0 NOT NULL,
                error_code VARCHAR(50),
                error_message TEXT,
                started_at DATETIME,
                completed_at DATETIME,
                verified_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_restore_items_id ON restore_items (id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_restore_items_restore_job_id ON restore_items (restore_job_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_restore_items_backup_file_id ON restore_items (backup_file_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_restore_items_status ON restore_items (status)")

        # 3. Create restore_checkpoints table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS restore_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restore_job_id INTEGER NOT NULL REFERENCES restore_jobs(id) ON DELETE CASCADE,
                last_completed_item_id INTEGER,
                completed_items_count INTEGER DEFAULT 0 NOT NULL,
                bytes_restored BIGINT DEFAULT 0 NOT NULL,
                checkpoint_version INTEGER DEFAULT 1 NOT NULL,
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_restore_checkpoints_id ON restore_checkpoints (id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_restore_checkpoints_restore_job_id ON restore_checkpoints (restore_job_id)")

        con.commit()
        con.close()
        print(f"V6 migration successfully applied to: {db_path}")


if __name__ == "__main__":
    run_migration()

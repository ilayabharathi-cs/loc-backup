"""Database migration helper for V4 Reliability schema."""

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
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # 1. Update backup_runs
        cols_run = [c[1] for c in cur.execute("PRAGMA table_info(backup_runs)")]
        if "state" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN state VARCHAR(30) DEFAULT 'CREATED'")
        if "lease_id" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN lease_id VARCHAR(100)")
        if "lease_expires_at" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN lease_expires_at DATETIME")
        if "interrupted_at" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN interrupted_at DATETIME")
        if "resumed_at" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN resumed_at DATETIME")
        if "checkpoint_version" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN checkpoint_version INTEGER DEFAULT 1")
        if "retry_count" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN retry_count INTEGER DEFAULT 0")
        if "files_locked" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN files_locked INTEGER DEFAULT 0")
        if "files_vss_recovered" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN files_vss_recovered INTEGER DEFAULT 0")
        if "files_skipped" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN files_skipped INTEGER DEFAULT 0")

        # 2. Create upload_sessions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS upload_sessions (
                id VARCHAR(64) PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES backup_runs(id) ON DELETE CASCADE,
                object_id VARCHAR(255) NOT NULL,
                file_path VARCHAR(1000) NOT NULL,
                relative_path VARCHAR(1000),
                change_type VARCHAR(20) DEFAULT 'FULL',
                total_size BIGINT NOT NULL,
                chunk_size INTEGER DEFAULT 4194304,
                total_chunks INTEGER NOT NULL,
                received_bytes BIGINT DEFAULT 0,
                next_chunk_index INTEGER DEFAULT 0,
                file_mtime DATETIME,
                expected_sha256 VARCHAR(64),
                final_sha256 VARCHAR(64),
                status VARCHAR(20) DEFAULT 'active',
                staging_path VARCHAR(1000),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_upload_sessions_run_id ON upload_sessions (run_id)")

        # 3. Create upload_chunks
        cur.execute("""
            CREATE TABLE IF NOT EXISTS upload_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_session_id VARCHAR(64) NOT NULL REFERENCES upload_sessions(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                offset BIGINT NOT NULL,
                size INTEGER NOT NULL,
                sha256 VARCHAR(64) NOT NULL,
                status VARCHAR(20) DEFAULT 'persisted',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (upload_session_id, chunk_index)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_upload_chunks_session_id ON upload_chunks (upload_session_id)")

        # 4. Create backup_checkpoints
        cur.execute("""
            CREATE TABLE IF NOT EXISTS backup_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES backup_runs(id) ON DELETE CASCADE,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                current_file VARCHAR(1000),
                bytes_uploaded BIGINT DEFAULT 0,
                last_chunk_index INTEGER DEFAULT 0,
                state VARCHAR(30) DEFAULT 'BACKING_UP',
                checkpoint_version INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_backup_checkpoints_run_id ON backup_checkpoints (run_id)")

        # 5. Create run_events
        cur.execute("""
            CREATE TABLE IF NOT EXISTS run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES backup_runs(id) ON DELETE CASCADE,
                event_type VARCHAR(50) NOT NULL,
                message VARCHAR(1000) NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                event_metadata TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_run_events_run_id ON run_events (run_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_run_events_event_type ON run_events (event_type)")

        con.commit()
        con.close()
        print(f"Applied V4 schema migration to: {db_path}")


if __name__ == "__main__":
    run_migration()

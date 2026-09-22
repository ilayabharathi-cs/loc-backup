"""Database migration helper for V2 Initial Full Backup schema."""

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
        if "policy_id" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN policy_id INTEGER REFERENCES backup_policies(id) ON DELETE SET NULL")
        if "files_discovered" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN files_discovered INTEGER DEFAULT 0")
        if "files_uploaded" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN files_uploaded INTEGER DEFAULT 0")
        if "files_failed" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN files_failed INTEGER DEFAULT 0")
        if "bytes_total" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN bytes_total BIGINT DEFAULT 0")

        # 2. Update backup_files
        cols_files = [c[1] for c in cur.execute("PRAGMA table_info(backup_files)")]
        if "relative_path" not in cols_files:
            cur.execute("ALTER TABLE backup_files ADD COLUMN relative_path VARCHAR(1000)")
        if "upload_status" not in cols_files:
            cur.execute("ALTER TABLE backup_files ADD COLUMN upload_status VARCHAR(50) DEFAULT 'completed'")
        if "modified_time" not in cols_files:
            cur.execute("ALTER TABLE backup_files ADD COLUMN modified_time TIMESTAMP")

        con.commit()
        con.close()
        print(f"Applied V2 schema migration to: {db_path}")

if __name__ == "__main__":
    run_migration()

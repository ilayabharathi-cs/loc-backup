"""Database migration helper for V3 Incremental Backup schema."""

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
        if "files_new" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN files_new INTEGER DEFAULT 0")
        if "files_modified" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN files_modified INTEGER DEFAULT 0")
        if "files_unchanged" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN files_unchanged INTEGER DEFAULT 0")
        if "files_deleted" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN files_deleted INTEGER DEFAULT 0")
        if "baseline_run_id" not in cols_run:
            cur.execute("ALTER TABLE backup_runs ADD COLUMN baseline_run_id INTEGER REFERENCES backup_runs(id) ON DELETE SET NULL")

        # 2. Update backup_files
        cols_files = [c[1] for c in cur.execute("PRAGMA table_info(backup_files)")]
        if "change_type" not in cols_files:
            cur.execute("ALTER TABLE backup_files ADD COLUMN change_type VARCHAR(20) DEFAULT 'FULL'")

        # 3. Update backup_jobs
        cols_jobs = [c[1] for c in cur.execute("PRAGMA table_info(backup_jobs)")]
        if "backup_type" not in cols_jobs:
            cur.execute("ALTER TABLE backup_jobs ADD COLUMN backup_type VARCHAR(20) DEFAULT 'full'")

        # 4. Update recovery_points
        cols_rp = [c[1] for c in cur.execute("PRAGMA table_info(recovery_points)")]
        if "backup_type" not in cols_rp:
            cur.execute("ALTER TABLE recovery_points ADD COLUMN backup_type VARCHAR(20) DEFAULT 'full'")

        con.commit()
        con.close()
        print(f"Applied V3 schema migration to: {db_path}")

if __name__ == "__main__":
    run_migration()

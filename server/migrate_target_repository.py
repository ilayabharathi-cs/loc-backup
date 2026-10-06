"""Database migration runner to add target_repository column to backup_policies and backup_runs."""

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

        # Check backup_policies
        cur.execute("PRAGMA table_info(backup_policies)")
        cols = [r[1] for r in cur.fetchall()]
        if "target_repository" not in cols:
            print("  [+] Adding target_repository column to backup_policies...")
            cur.execute("ALTER TABLE backup_policies ADD COLUMN target_repository VARCHAR(100) DEFAULT 'repository'")
        else:
            print("  [*] target_repository column already exists in backup_policies")

        # Check backup_runs
        cur.execute("PRAGMA table_info(backup_runs)")
        run_cols = [r[1] for r in cur.fetchall()]
        if "target_repository" not in run_cols:
            print("  [+] Adding target_repository column to backup_runs...")
            cur.execute("ALTER TABLE backup_runs ADD COLUMN target_repository VARCHAR(100) DEFAULT 'repository'")
        else:
            print("  [*] target_repository column already exists in backup_runs")

        con.commit()
        con.close()
        print("  [SUCCESS] Migration completed for:", db_path)

if __name__ == "__main__":
    run_migration()

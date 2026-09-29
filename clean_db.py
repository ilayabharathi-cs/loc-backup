import sqlite3
import os
import shutil

db_paths = [
    os.path.abspath("server/backup.db"),
    os.path.abspath("backup.db")
]

tables = [
    "clients", "backup_jobs", "backup_runs", "backup_files", 
    "recovery_points", "restore_jobs", "restore_items", 
    "audit_logs", "alerts", "storage_objects",
    "upload_sessions", "upload_chunks", "backup_checkpoints", "run_events"
]

for dbp in db_paths:
    if os.path.exists(dbp):
        conn = sqlite3.connect(dbp)
        cur = conn.cursor()
        for t in tables:
            try:
                cur.execute(f'DELETE FROM "{t}"')
            except Exception as e:
                pass
        conn.commit()
        cur.execute("VACUUM")
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM clients")
        print(f"Cleaned {dbp}: clients={cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM backup_jobs")
        print(f"Cleaned {dbp}: jobs={cur.fetchone()[0]}")
        conn.close()

# Also clean repository objects/clients/quarantine
repo_dir = os.path.abspath("repository")
for sub in ["objects", "clients", "quarantine"]:
    p = os.path.join(repo_dir, sub)
    if os.path.exists(p):
        for item in os.listdir(p):
            ipath = os.path.join(p, item)
            try:
                if os.path.isdir(ipath):
                    shutil.rmtree(ipath)
                else:
                    os.remove(ipath)
            except Exception:
                pass
print("Repository storage completely clean.")

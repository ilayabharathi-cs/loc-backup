"""Database migration runner for RetroVault V9 High Availability & Distributed Control Plane."""

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
        print(f"Migrating database for V9 High Availability: {db_path}")
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # 1. Create cluster_nodes table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cluster_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id VARCHAR(100) UNIQUE NOT NULL,
                hostname VARCHAR(150) NOT NULL,
                ip_address VARCHAR(60) NOT NULL,
                role VARCHAR(50) DEFAULT 'CONTROL_PLANE' NOT NULL,
                status VARCHAR(30) DEFAULT 'STARTING' NOT NULL,
                version VARCHAR(30) DEFAULT '9.0.0' NOT NULL,
                capabilities_json TEXT,
                last_heartbeat DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                draining_started_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cluster_nodes_node_id ON cluster_nodes (node_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cluster_nodes_status ON cluster_nodes (status)")

        # 2. Create cluster_leases table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cluster_leases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lease_key VARCHAR(100) UNIQUE NOT NULL,
                owner_node_id VARCHAR(100) NOT NULL,
                lease_token VARCHAR(100) NOT NULL,
                lease_expires_at DATETIME NOT NULL,
                acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                renewed_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cluster_leases_key ON cluster_leases (lease_key)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cluster_leases_owner ON cluster_leases (owner_node_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cluster_leases_expires ON cluster_leases (lease_expires_at)")

        # 3. Create distributed_jobs table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS distributed_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type VARCHAR(50) NOT NULL,
                priority VARCHAR(20) DEFAULT 'NORMAL' NOT NULL,
                priority_weight INTEGER DEFAULT 10 NOT NULL,
                status VARCHAR(30) DEFAULT 'QUEUED' NOT NULL,
                owner_node_id VARCHAR(100),
                client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                repository_id INTEGER REFERENCES storage_repositories(id) ON DELETE SET NULL,
                run_id INTEGER REFERENCES backup_runs(id) ON DELETE SET NULL,
                payload_json TEXT,
                attempt_count INTEGER DEFAULT 0 NOT NULL,
                max_attempts INTEGER DEFAULT 3 NOT NULL,
                available_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                started_at DATETIME,
                heartbeat_at DATETIME,
                completed_at DATETIME,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_distributed_jobs_type ON distributed_jobs (job_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_distributed_jobs_status ON distributed_jobs (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_distributed_jobs_owner ON distributed_jobs (owner_node_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_distributed_jobs_client ON distributed_jobs (client_id)")

        # 4. Create distributed_locks table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS distributed_locks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_key VARCHAR(200) UNIQUE NOT NULL,
                lock_type VARCHAR(50) NOT NULL,
                owner_node_id VARCHAR(100) NOT NULL,
                lock_token VARCHAR(100) NOT NULL,
                expires_at DATETIME NOT NULL,
                acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_distributed_locks_key ON distributed_locks (resource_key)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_distributed_locks_expires ON distributed_locks (expires_at)")

        # 5. Create cluster_events table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cluster_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type VARCHAR(60) NOT NULL,
                severity VARCHAR(20) DEFAULT 'INFO' NOT NULL,
                node_id VARCHAR(100),
                details_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cluster_events_type ON cluster_events (event_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_cluster_events_severity ON cluster_events (severity)")

        # 6. Create bulk_operations table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bulk_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id VARCHAR(50) UNIQUE NOT NULL,
                operation_type VARCHAR(60) NOT NULL,
                status VARCHAR(30) DEFAULT 'PENDING' NOT NULL,
                target_count INTEGER DEFAULT 0 NOT NULL,
                success_count INTEGER DEFAULT 0 NOT NULL,
                failure_count INTEGER DEFAULT 0 NOT NULL,
                skipped_count INTEGER DEFAULT 0 NOT NULL,
                details_json TEXT,
                started_at DATETIME,
                completed_at DATETIME,
                created_by VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_bulk_operations_op_id ON bulk_operations (operation_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_bulk_operations_status ON bulk_operations (status)")

        con.commit()
        con.close()
        print(f"V9 migration successfully applied to: {db_path}")


if __name__ == "__main__":
    run_migration()

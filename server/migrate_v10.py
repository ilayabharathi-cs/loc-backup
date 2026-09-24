"""Database migration runner for RetroVault V10 Operational Intelligence, Observability, Capacity & Compliance."""

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
        print(f"Migrating database for V10 Operational Intelligence: {db_path}")
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # 1. metric_samples
        cur.execute("""
            CREATE TABLE IF NOT EXISTS metric_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name VARCHAR(100) NOT NULL,
                value REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                source VARCHAR(100) NOT NULL,
                labels_json TEXT,
                granularity VARCHAR(20) DEFAULT 'RAW' NOT NULL,
                sample_count INTEGER DEFAULT 1 NOT NULL,
                min_value REAL,
                max_value REAL,
                sum_value REAL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_metric_samples_name ON metric_samples (metric_name)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_metric_samples_timestamp ON metric_samples (timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_metric_samples_source ON metric_samples (source)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_metric_samples_granularity ON metric_samples (granularity)")

        # 2. health_checks
        cur.execute("""
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component VARCHAR(80) NOT NULL,
                check_type VARCHAR(30) DEFAULT 'liveness' NOT NULL,
                status VARCHAR(30) NOT NULL,
                latency_ms REAL DEFAULT 0.0 NOT NULL,
                last_success DATETIME,
                last_failure DATETIME,
                reason TEXT,
                details_json TEXT,
                checked_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_health_checks_component ON health_checks (component)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_health_checks_status ON health_checks (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_health_checks_checked_at ON health_checks (checked_at)")

        # 3. operational_alerts
        cur.execute("""
            CREATE TABLE IF NOT EXISTS operational_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id VARCHAR(100) UNIQUE NOT NULL,
                alert_type VARCHAR(80) NOT NULL,
                severity VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL,
                source VARCHAR(80) NOT NULL,
                resource_id VARCHAR(150) NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                evidence_json TEXT,
                threshold_value REAL,
                observed_value REAL,
                fingerprint VARCHAR(120) NOT NULL,
                occurrence_count INTEGER DEFAULT 1 NOT NULL,
                first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                acknowledged_at DATETIME,
                acknowledged_by VARCHAR(100),
                resolved_at DATETIME,
                resolved_by VARCHAR(100),
                incident_id VARCHAR(100)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_alerts_alert_id ON operational_alerts (alert_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_alerts_type ON operational_alerts (alert_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_alerts_severity ON operational_alerts (severity)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_alerts_status ON operational_alerts (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_alerts_source ON operational_alerts (source)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_alerts_resource_id ON operational_alerts (resource_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_alerts_fingerprint ON operational_alerts (fingerprint)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_alerts_incident_id ON operational_alerts (incident_id)")

        # 4. operational_incidents
        cur.execute("""
            CREATE TABLE IF NOT EXISTS operational_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id VARCHAR(100) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                status VARCHAR(30) DEFAULT 'DETECTED' NOT NULL,
                severity VARCHAR(20) NOT NULL,
                root_event VARCHAR(255) NOT NULL,
                relationship_type VARCHAR(50) DEFAULT 'CAUSAL' NOT NULL,
                affected_resources_json TEXT NOT NULL DEFAULT '[]',
                child_alerts_json TEXT NOT NULL DEFAULT '[]',
                timeline_json TEXT,
                evidence_json TEXT,
                mitigation_steps TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                resolved_at DATETIME,
                resolved_by VARCHAR(100)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_incidents_incident_id ON operational_incidents (incident_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_incidents_status ON operational_incidents (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_incidents_severity ON operational_incidents (severity)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_operational_incidents_created_at ON operational_incidents (created_at)")

        # 5. capacity_snapshots
        cur.execute("""
            CREATE TABLE IF NOT EXISTS capacity_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repository_id INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                logical_bytes INTEGER DEFAULT 0 NOT NULL,
                unique_content_bytes INTEGER DEFAULT 0 NOT NULL,
                compressed_bytes INTEGER DEFAULT 0 NOT NULL,
                physical_bytes INTEGER DEFAULT 0 NOT NULL,
                free_bytes INTEGER DEFAULT 0 NOT NULL,
                total_capacity_bytes INTEGER DEFAULT 0 NOT NULL,
                utilization_pct REAL DEFAULT 0.0 NOT NULL,
                dedup_ratio REAL DEFAULT 1.0 NOT NULL,
                compression_ratio REAL DEFAULT 1.0 NOT NULL,
                overall_efficiency REAL DEFAULT 1.0 NOT NULL,
                daily_growth_bytes INTEGER DEFAULT 0 NOT NULL,
                weekly_growth_bytes INTEGER DEFAULT 0 NOT NULL,
                monthly_growth_bytes INTEGER DEFAULT 0 NOT NULL,
                FOREIGN KEY (repository_id) REFERENCES storage_repositories (id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_capacity_snapshots_repo ON capacity_snapshots (repository_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_capacity_snapshots_timestamp ON capacity_snapshots (timestamp)")

        # 6. capacity_forecasts
        cur.execute("""
            CREATE TABLE IF NOT EXISTS capacity_forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repository_id INTEGER NOT NULL,
                generated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                method VARCHAR(50) NOT NULL,
                status VARCHAR(30) DEFAULT 'PROJECTED' NOT NULL,
                data_window_days INTEGER DEFAULT 30 NOT NULL,
                sample_count INTEGER DEFAULT 0 NOT NULL,
                daily_burn_rate_bytes REAL DEFAULT 0.0 NOT NULL,
                days_to_depletion REAL,
                estimated_depletion_date DATETIME,
                forecast_7d_bytes INTEGER,
                forecast_30d_bytes INTEGER,
                forecast_90d_bytes INTEGER,
                confidence_metric REAL,
                uncertainty_info_json TEXT,
                is_projection BOOLEAN DEFAULT 1 NOT NULL,
                FOREIGN KEY (repository_id) REFERENCES storage_repositories (id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_capacity_forecasts_repo ON capacity_forecasts (repository_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_capacity_forecasts_generated_at ON capacity_forecasts (generated_at)")

        # 7. compliance_evidence
        cur.execute("""
            CREATE TABLE IF NOT EXISTS compliance_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id VARCHAR(100) UNIQUE NOT NULL,
                domain VARCHAR(60) NOT NULL,
                status VARCHAR(40) NOT NULL,
                resource_type VARCHAR(60) NOT NULL,
                resource_id VARCHAR(150) NOT NULL,
                period_start DATETIME NOT NULL,
                period_end DATETIME NOT NULL,
                evidence_summary TEXT NOT NULL,
                evidence_payload_json TEXT,
                verification_hash VARCHAR(128) NOT NULL,
                evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_compliance_evidence_id ON compliance_evidence (evidence_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_compliance_evidence_domain ON compliance_evidence (domain)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_compliance_evidence_status ON compliance_evidence (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_compliance_evidence_resource ON compliance_evidence (resource_type, resource_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_compliance_evidence_period ON compliance_evidence (period_start, period_end)")

        # 8. compliance_reports
        cur.execute("""
            CREATE TABLE IF NOT EXISTS compliance_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id VARCHAR(100) UNIQUE NOT NULL,
                report_type VARCHAR(60) NOT NULL,
                title VARCHAR(255) NOT NULL,
                period_start DATETIME NOT NULL,
                period_end DATETIME NOT NULL,
                scope VARCHAR(100) DEFAULT 'GLOBAL' NOT NULL,
                data_sources_json TEXT NOT NULL,
                system_version VARCHAR(30) DEFAULT '10.0.0' NOT NULL,
                evidence_summary_json TEXT NOT NULL,
                exceptions_json TEXT,
                unknowns_json TEXT,
                generated_by VARCHAR(100) DEFAULT 'SYSTEM' NOT NULL,
                generated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_compliance_reports_id ON compliance_reports (report_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_compliance_reports_type ON compliance_reports (report_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_compliance_reports_generated_at ON compliance_reports (generated_at)")

        # 9. report_executions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS report_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id VARCHAR(100) UNIQUE NOT NULL,
                report_id VARCHAR(100) NOT NULL,
                format VARCHAR(20) NOT NULL,
                status VARCHAR(30) DEFAULT 'COMPLETED' NOT NULL,
                file_path VARCHAR(255),
                file_size_bytes INTEGER DEFAULT 0 NOT NULL,
                checksum_sha256 VARCHAR(64),
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_report_executions_id ON report_executions (execution_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_report_executions_report_id ON report_executions (report_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_report_executions_format ON report_executions (format)")

        con.commit()
        con.close()
        print(f"Successfully applied V10 migration to {db_path}")


if __name__ == "__main__":
    run_migration()

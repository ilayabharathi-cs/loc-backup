"""Tests for RetroVault V10 Compliance Evidence, Enterprise Reports & Recommendations."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.services.observability.compliance_service import ComplianceEvidenceService
from app.services.observability.report_generator import ReportGeneratorService
from app.services.observability.recommendations import RecommendationEngine

client = TestClient(app)


@pytest.fixture
def auth_headers():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPass123!"})
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_compliance_evidence_evaluation():
    db = SessionLocal()
    try:
        service = ComplianceEvidenceService(db)
        evidence_items = service.evaluate_all_domains()

        assert len(evidence_items) == 13
        for item in evidence_items:
            assert item.domain is not None
            assert item.status in ["EVIDENCE_AVAILABLE", "EVIDENCE_MISSING", "NOT_APPLICABLE", "UNKNOWN"]
            assert item.verification_hash is not None
            assert len(item.verification_hash) == 64  # SHA-256 hex
    finally:
        db.close()


def test_report_generation_and_multi_format_export():
    db = SessionLocal()
    try:
        generator = ReportGeneratorService(db)

        # 1. Compile report
        report = generator.generate_report(
            report_type="comprehensive_compliance",
            title="Q3 Comprehensive Compliance Audit"
        )
        assert report.report_id.startswith("RPT-")
        assert report.system_version == "10.0.0"

        # 2. Export to JSON
        json_exec = generator.export_report(report.report_id, "JSON")
        assert json_exec.format == "JSON"
        assert json_exec.file_size_bytes > 0
        assert json_exec.checksum_sha256 is not None
        assert os.path.exists(json_exec.file_path)

        # 3. Export to CSV
        csv_exec = generator.export_report(report.report_id, "CSV")
        assert csv_exec.format == "CSV"
        assert csv_exec.file_size_bytes > 0
        assert os.path.exists(csv_exec.file_path)

        # 4. Export to PDF
        pdf_exec = generator.export_report(report.report_id, "PDF")
        assert pdf_exec.format == "PDF"
        assert pdf_exec.file_size_bytes > 0
        assert os.path.exists(pdf_exec.file_path)
    finally:
        db.close()


def test_recommendation_engine_explainability():
    db = SessionLocal()
    try:
        engine = RecommendationEngine(db)
        recs = engine.evaluate_recommendations()

        for r in recs:
            assert "id" in r
            assert "severity" in r
            assert "reason" in r
            assert "evidence" in r
            assert "recommended_action" in r
            assert r["is_automated_execution_allowed"] is False
    finally:
        db.close()


def test_compliance_and_reports_rest_api(auth_headers):
    # 1. Compliance summary
    c_res = client.get("/api/v1/compliance/", headers=auth_headers)
    assert c_res.status_code == 200
    assert "domains_total" in c_res.json()
    assert c_res.json()["domains_total"] == 13

    # 2. Generate report
    rep_res = client.post("/api/v1/reports/", json={
        "report_type": "backup_operations",
        "title": "Weekly Operations Audit"
    }, headers=auth_headers)
    assert rep_res.status_code == 200
    rep_id = rep_res.json()["report_id"]

    # 3. Export report to JSON, CSV, PDF
    for fmt in ["JSON", "CSV", "PDF"]:
        exp_res = client.post(f"/api/v1/reports/{rep_id}/export", json={"format": fmt}, headers=auth_headers)
        assert exp_res.status_code == 200
        assert exp_res.json()["format"] == fmt

    # 4. Download report
    down_res = client.get(f"/api/v1/reports/{rep_id}/download?format=PDF", headers=auth_headers)
    assert down_res.status_code == 200
    assert down_res.headers["content-type"] == "application/pdf"

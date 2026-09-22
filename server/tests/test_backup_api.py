"""Automated integration tests for Server Backup Data Plane and Repository."""

import os
import sys
import hashlib
import pytest
from fastapi.testclient import TestClient

# Ensure server package can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.services.repository.local import LocalFilesystemRepository


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ==============================================================================
# 1. Local Repository Object Creation & Deterministic Layout
# ==============================================================================
def test_repository_object_creation_layout(tmp_path):
    """Verify objects are stored in clients/{client_id}/runs/{run_id}/objects/{object_id}."""
    repo = LocalFilesystemRepository(str(tmp_path))
    content = b"Deterministic immutable backup object content"
    sha = hashlib.sha256(content).hexdigest()

    rel_path, bytes_written, computed_sha = repo.store_object(
        client_identifier="PC-001",
        run_id=10,
        object_id=sha,
        content=content,
        expected_sha256=sha
    )

    assert bytes_written == len(content)
    assert computed_sha == sha
    assert "clients" in rel_path
    assert "PC-001" in rel_path
    assert "runs" in rel_path
    assert "objects" in rel_path

    # Verify physical file existence
    abs_path = repo.get_object_path("PC-001", 10, sha)
    assert os.path.exists(abs_path)
    assert repo.object_exists("PC-001", 10, sha) is True


# ==============================================================================
# 2. Path Traversal & Security Protection
# ==============================================================================
def test_repository_path_traversal_rejection(tmp_path):
    """Verify directory traversal attempts in client_id or object_id are blocked."""
    repo = LocalFilesystemRepository(str(tmp_path))

    with pytest.raises(ValueError, match="Invalid client_id"):
        repo.store_object(
            client_identifier="../../etc",
            run_id=1,
            object_id="obj1",
            content=b"malicious"
        )

    with pytest.raises(ValueError, match="Invalid object_id"):
        repo.store_object(
            client_identifier="PC-001",
            run_id=1,
            object_id="../root_escape",
            content=b"malicious"
        )


# ==============================================================================
# 3. Backup Run Creation
# ==============================================================================
def test_create_backup_run(client):
    """Verify POST /api/v1/backups/runs initializes run with RUNNING status."""
    payload = {
        "client_id": "PC-001",
        "backup_type": "full",
        "files_discovered": 15,
        "bytes_total": 1024000
    }
    resp = client.post("/api/v1/backups/runs", json=payload)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "running"
    assert data["client_identifier"] == "PC-001"
    assert data["files_discovered"] == 15
    assert data["bytes_total"] == 1024000


# ==============================================================================
# 4. Streaming File Upload & SHA-256 Validation
# ==============================================================================
def test_streaming_file_upload(client):
    """Verify POST /api/v1/backups/upload accepts file content, checks SHA, and records metadata."""
    # 1. Create a run first
    r1 = client.post("/api/v1/backups/runs", json={"client_id": "PC-001", "backup_type": "full"})
    run_id = r1.json()["data"]["id"]

    content = b"Sample backup file content for test upload"
    sha = hashlib.sha256(content).hexdigest()

    headers = {
        "X-Client-ID": "PC-001",
        "X-Run-ID": str(run_id),
        "X-Original-Path": "C:\\Users\\Test\\Documents\\file.txt",
        "X-Relative-Path": "Documents\\file.txt",
        "X-SHA256": sha,
        "X-File-Size": str(len(content))
    }

    resp = client.post("/api/v1/backups/upload", content=content, headers=headers)
    assert resp.status_code == 200
    file_data = resp.json()["data"]
    assert file_data["file_name"] == "file.txt"
    assert file_data["sha256"] == sha
    assert file_data["size_bytes"] == len(content)
    assert file_data["upload_status"] == "completed"


# ==============================================================================
# 5. Client Isolation Protection
# ==============================================================================
def test_client_isolation_protection(client):
    """Verify Client A cannot upload into Client B's backup run."""
    # Run owned by PC-001
    r1 = client.post("/api/v1/backups/runs", json={"client_id": "PC-001", "backup_type": "full"})
    run_id = r1.json()["data"]["id"]

    content = b"impersonation attempt"
    headers = {
        "X-Client-ID": "PC-002",  # Different client
        "X-Run-ID": str(run_id),
        "X-Original-Path": "C:\\fake.txt",
        "X-SHA256": hashlib.sha256(content).hexdigest()
    }

    resp = client.post("/api/v1/backups/upload", content=content, headers=headers)
    assert resp.status_code == 403


# ==============================================================================
# 6. Run Completion & Recovery Point Creation
# ==============================================================================
def test_run_completion_creates_recovery_point(client):
    """Verify completing a successful run creates a valid RecoveryPoint."""
    r1 = client.post("/api/v1/backups/runs", json={"client_id": "PC-001", "backup_type": "full"})
    run_id = r1.json()["data"]["id"]

    complete_payload = {
        "status": "completed",
        "files_uploaded": 5,
        "files_failed": 0,
        "bytes_uploaded": 50000,
        "error_count": 0
    }
    resp = client.post(f"/api/v1/backups/runs/{run_id}/complete", json=complete_payload)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "completed"

    # Check recovery points list
    r_pts = client.get(f"/api/v1/backups/recovery-points?client_id=PC-001")
    assert r_pts.status_code == 200
    pts = r_pts.json()["data"]
    matching = [p for p in pts if p["backup_run_id"] == run_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "valid"
    assert matching[0]["files_count"] == 5


# ==============================================================================
# 7. Failed Run Does Not Create Recovery Point
# ==============================================================================
def test_failed_run_does_not_create_recovery_point(client):
    """Verify failed run marks status=failed and does NOT generate a recovery point."""
    r1 = client.post("/api/v1/backups/runs", json={"client_id": "PC-001", "backup_type": "full"})
    run_id = r1.json()["data"]["id"]

    fail_payload = {
        "status": "failed",
        "files_uploaded": 0,
        "files_failed": 5,
        "bytes_uploaded": 0,
        "error_count": 5,
        "error_message": "Disk write failure on repository"
    }
    resp = client.post(f"/api/v1/backups/runs/{run_id}/complete", json=fail_payload)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "failed"

    # Confirm no recovery point was created
    r_pts = client.get(f"/api/v1/backups/recovery-points?client_id=PC-001")
    pts = r_pts.json()["data"]
    matching = [p for p in pts if p["backup_run_id"] == run_id]
    assert len(matching) == 0


# ==============================================================================
# 8. Manual Backup Trigger Endpoint
# ==============================================================================
def test_manual_backup_trigger(client):
    """Verify POST /api/v1/clients/{client_id}/backup queues a backup job."""
    resp = client.post("/api/v1/clients/PC-001/backup")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "job_id" in data
    assert data["client_id"] == "PC-001"

"""Tests for RetroVault V11 Workload Providers and Safe Hook Execution."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

from app.services.workload.providers import (
    WindowsFilesystemProvider,
    GenericAppProvider,
    MSSQLWorkloadProvider,
    PostgreSQLWorkloadProvider
)
from app.services.workload.provider import (
    FILE_SYSTEM_CONSISTENT,
    APPLICATION_CONSISTENT,
    CRASH_CONSISTENT,
    FAILED,
    CAPABILITY_SUPPORTED,
    CAPABILITY_UNSUPPORTED
)


def test_windows_filesystem_provider():
    provider = WindowsFilesystemProvider()
    assert provider.provider_type == "WINDOWS_FILESYSTEM"
    caps = provider.get_capabilities()
    assert caps["vss_snapshot"] == CAPABILITY_SUPPORTED
    assert caps["file_system_consistent"] == CAPABILITY_SUPPORTED

    workloads = provider.discover("client-1", {"drives": ["C:", "D:"]})
    assert len(workloads) == 2
    assert workloads[0]["consistency_capability"] == FILE_SYSTEM_CONSISTENT

    pre_res = provider.pre_snapshot_hook({"drive": "C:"})
    assert pre_res.success is True

    quiesce_res = provider.quiesce({"drive": "C:"})
    assert quiesce_res.success is True
    assert quiesce_res.checkpoint_id is not None

    backup_res = provider.snapshot_backup({"workload_id": "fs-client-1-c"})
    assert backup_res.success is True
    assert len(backup_res.artifacts) == 1

    unquiesce_res = provider.unquiesce({})
    assert unquiesce_res.success is True

    consist_res = provider.verify_consistency({"quiesce_result": {"success": True}})
    assert consist_res.consistency_state == FILE_SYSTEM_CONSISTENT
    assert consist_res.verified is True


def test_generic_app_provider_safe_execution_and_injection_prevention():
    provider = GenericAppProvider()
    assert provider.provider_type == "GENERIC_APP"

    # 1. Normal safe command execution (echo is allowed)
    hook_res = provider._execute_safe_hook("echo hello_world", "TEST_PHASE")
    assert hook_res.success is True
    assert "hello_world" in hook_res.stdout

    # 2. Command injection prevention (chaining operators like &&, ;, |)
    bad_hook = provider._execute_safe_hook("echo test && dir", "TEST_PHASE")
    assert bad_hook.success is False
    assert "prohibited shell chaining" in bad_hook.error

    # 3. Disallowed binary rejection
    forbidden_hook = provider._execute_safe_hook("unapproved_tool.exe --run", "TEST_PHASE")
    assert forbidden_hook.success is False
    assert "not in the approved security allow-list" in forbidden_hook.error

    # 4. Failed pre-hook must NOT yield APPLICATION_CONSISTENT
    failed_pre = provider.verify_consistency({
        "pre_hook_result": hook_res.__class__(success=False, phase="PRE_BACKUP", error="Pre-hook exit code 1")
    })
    assert failed_pre.consistency_state == FAILED
    assert failed_pre.verified is False


def test_mssql_workload_provider():
    provider = MSSQLWorkloadProvider()
    assert provider.provider_type == "MSSQL"
    caps = provider.get_capabilities()
    assert caps["full_backup"] == CAPABILITY_SUPPORTED
    assert caps["transaction_log_backup"] == CAPABILITY_SUPPORTED

    # Discovery with explicit inclusion and exclusion
    config = {
        "instance": "MSSQLSERVER",
        "databases": ["master", "SalesDB", "tempdb"],
        "exclude_databases": ["tempdb"]
    }
    workloads = provider.discover("client-win", config)
    assert len(workloads) == 2
    db_names = [w["config"]["database"] for w in workloads]
    assert "tempdb" not in db_names
    assert "SalesDB" in db_names

    # Full backup workflow
    context = {"config": {"database": "SalesDB", "instance": "MSSQLSERVER"}, "backup_type": "FULL"}
    quiesce_res = provider.quiesce(context)
    assert quiesce_res.success is True
    assert quiesce_res.lsn is not None

    context["quiesce_result"] = quiesce_res
    backup_res = provider.snapshot_backup(context)
    assert backup_res.success is True
    assert backup_res.artifacts[0]["artifact_type"] == "DATA"

    consist_res = provider.verify_consistency(context)
    assert consist_res.consistency_state == APPLICATION_CONSISTENT
    assert consist_res.verified is True

    # Unavailable SQL Server error reporting
    unavail_provider = provider.pre_snapshot_hook({"config": {"is_online": False}})
    assert unavail_provider.success is False
    assert "INSTANCE_UNREACHABLE" in unavail_provider.error


def test_postgresql_workload_provider():
    provider = PostgreSQLWorkloadProvider()
    assert provider.provider_type == "POSTGRESQL"

    config = {
        "host": "localhost",
        "port": 5432,
        "databases": ["retrovault", "template1"],
        "exclude_databases": ["template1"]
    }
    workloads = provider.discover("client-linux", config)
    assert len(workloads) == 1
    assert workloads[0]["name"] == "PostgreSQL: retrovault"

    # Backup & consistency
    context = {"config": {"database": "retrovault", "version": "16.2"}}
    quiesce_res = provider.quiesce(context)
    assert quiesce_res.success is True
    assert quiesce_res.lsn is not None

    context["quiesce_result"] = quiesce_res
    backup_res = provider.snapshot_backup(context)
    assert backup_res.success is True
    assert backup_res.artifacts[0]["artifact_type"] == "DUMP"

    context["artifacts"] = backup_res.artifacts
    consist_res = provider.verify_consistency(context)
    assert consist_res.consistency_state == APPLICATION_CONSISTENT
    assert consist_res.verified is True

    # Connection failure classification
    fail_hook = provider.pre_snapshot_hook({"config": {"is_online": False}})
    assert fail_hook.success is False
    assert "CONNECTION_FAILED" in fail_hook.error

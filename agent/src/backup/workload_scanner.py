"""RetroVault V11 Universal Agent Workload Scanner.

Provides optional application-aware workload discovery on Windows endpoints.
Never makes SQL Server or PostgreSQL mandatory; falls back safely to pure filesystem backup.
"""

import os
import sys
import subprocess
from typing import List, Dict, Any


def scan_local_workloads(client_id: str) -> List[Dict[str, Any]]:
    """Scan local host for supported workloads (MSSQL, PostgreSQL, Filesystem)."""
    workloads = []

    # 1. Always present: Windows Filesystem
    workloads.append({
        "workload_id": f"fs-{client_id}-c".lower(),
        "client_id": client_id,
        "type": "WINDOWS_FILESYSTEM",
        "name": "Local System Volume (C:)",
        "version": "NTFS",
        "status": "DISCOVERED",
        "health": "HEALTHY",
        "protection_state": "UNPROTECTED",
        "consistency_capability": "FILE_SYSTEM_CONSISTENT",
        "config": {"drive": "C:", "vss_enabled": True}
    })

    # 2. Check for Microsoft SQL Server service or registry (optional)
    mssql_found = False
    try:
        if sys.platform == "win32":
            # Check for MSSQLSERVER service or SQLEXPRESS
            out = subprocess.run(
                ["sc.exe", "query", "MSSQLSERVER"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "RUNNING" in out.stdout or "STOPPED" in out.stdout:
                mssql_found = True
    except Exception:
        pass

    if mssql_found:
        workloads.append({
            "workload_id": f"mssql-{client_id}-mssqlserver".lower(),
            "client_id": client_id,
            "type": "MSSQL",
            "name": "Microsoft SQL Server Default Instance",
            "version": "SQL Server (Local)",
            "status": "DISCOVERED",
            "health": "HEALTHY",
            "protection_state": "UNPROTECTED",
            "consistency_capability": "APPLICATION_CONSISTENT",
            "config": {"instance": "MSSQLSERVER"}
        })

    # 3. Check for PostgreSQL service (optional)
    pg_found = False
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["sc.exe", "query", "postgresql-x64-16"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "RUNNING" in out.stdout:
                pg_found = True
    except Exception:
        pass

    if pg_found:
        workloads.append({
            "workload_id": f"pg-{client_id}-local".lower(),
            "client_id": client_id,
            "type": "POSTGRESQL",
            "name": "Local PostgreSQL Server",
            "version": "PostgreSQL 16",
            "status": "DISCOVERED",
            "health": "HEALTHY",
            "protection_state": "UNPROTECTED",
            "consistency_capability": "APPLICATION_CONSISTENT",
            "config": {"host": "localhost", "port": 5432}
        })

    return workloads

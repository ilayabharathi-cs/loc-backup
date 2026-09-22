"""Dynamic System Discovery module for RetroVault Windows Backup Agent."""

import os
import sys
import socket
import platform
import datetime
from typing import Dict, Any, List
from agent.src.utils.windows import get_logical_drives, get_memory_info, is_windows


def get_local_ip_addresses() -> List[str]:
    """Dynamically discover non-loopback local IPv4 addresses."""
    ips = set()
    try:
        # Resolve hostname
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass

    # Quick connect probe to discover outbound default interface IP without sending traffic
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        outbound_ip = s.getsockname()[0]
        if outbound_ip and not outbound_ip.startswith("127."):
            ips.add(outbound_ip)
        s.close()
    except Exception:
        pass

    if not ips:
        ips.add("127.0.0.1")

    return sorted(list(ips))


def collect_system_info(device_id: str, agent_version: str = "1.0.0") -> Dict[str, Any]:
    """Collect comprehensive hardware, OS, and network telemetry dynamically."""
    hostname = platform.node() or socket.gethostname() or "UNKNOWN-HOST"
    
    # OS Information
    system_os = platform.system() or "Windows"
    os_release = platform.release()
    os_version_str = platform.version()
    architecture = platform.machine() or "x86_64"

    # CPU Information
    cpu_count = os.cpu_count() or 1
    cpu_model = platform.processor() or "Generic CPU"

    # Memory & Drives
    mem_info = get_memory_info()
    drives = get_logical_drives()

    # Dynamic local IPs
    ip_list = get_local_ip_addresses()
    primary_ip = ip_list[0] if ip_list else "127.0.0.1"

    # Approximate boot time
    boot_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return {
        "device_id": device_id,
        "hostname": hostname,
        "os": system_os,
        "os_release": os_release,
        "os_version": f"{os_release} (Build {os_version_str})",
        "architecture": architecture,
        "cpu_count": cpu_count,
        "cpu_model": cpu_model,
        "memory_total_bytes": mem_info["total_bytes"],
        "memory_available_bytes": mem_info["available_bytes"],
        "memory_used_percent": mem_info["used_percent"],
        "ip_address": primary_ip,
        "all_ip_addresses": ip_list,
        "drives": drives,
        "agent_version": agent_version,
        "boot_time": boot_time,
    }

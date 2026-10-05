"""Windows Startup Apps Persistence Module for RetroVault Backup Agent.

Ensures the agent executable automatically launches silently on Windows startup
(reboot, shutdown, login) without requiring interactive user consent.
Maintains persistent configuration across reboots.
"""

import os
import sys
import json
import shutil
from typing import Optional
from agent.src.logger import get_logger

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False


STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "RetroVaultAgent"


def get_current_executable() -> str:
    """Return the absolute canonical path to the agent executable or python script."""
    if getattr(sys, "frozen", False):
        # Compiled standalone PyInstaller .exe
        return os.path.abspath(sys.executable)
    else:
        # Running as python script
        main_script = os.path.abspath(sys.argv[0])
        return f'"{sys.executable}" "{main_script}"'


def get_user_startup_folder() -> Optional[str]:
    """Get the Windows user Startup folder path."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        startup_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        if os.path.exists(startup_dir) or os.path.exists(os.path.dirname(startup_dir)):
            os.makedirs(startup_dir, exist_ok=True)
            return startup_dir
    return None


def get_programdata_agent_dir() -> str:
    """Get ProgramData agent directory, creating it if needed."""
    programdata = os.environ.get("ProgramData") or os.environ.get("ALLUSERSPROFILE") or "C:\\ProgramData"
    target_dir = os.path.join(programdata, "RetroVault", "agent")
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception:
        pass
    return target_dir


def persist_config_file(source_config_path: Optional[str] = None) -> None:
    """
    Ensure the assigned server config.json is permanently persisted in ProgramData
    and AppData so that on reboot the startup app connects to the assigned server IP.
    """
    logger = get_logger()
    data = None

    # Candidate source locations
    candidates = []
    if source_config_path and os.path.exists(source_config_path):
        candidates.append(source_config_path)

    # Adjacent to executable
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "config.json"))

    # Workspace/agent root config.json
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates.append(os.path.join(script_dir, "config.json"))
    candidates.append(os.path.abspath("config.json"))

    # ProgramData existing config
    pd_dir = get_programdata_agent_dir()
    pd_config = os.path.join(pd_dir, "config.json")
    if os.path.exists(pd_config):
        candidates.append(pd_config)

    for c in candidates:
        if c and os.path.exists(c):
            try:
                with open(c, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data and "server_url" in data:
                    break
            except Exception:
                continue

    if not data:
        # Default fallback
        data = {
            "server_url": "http://192.168.0.131:8000",
            "heartbeat_interval_seconds": 30,
            "log_level": "INFO",
            "agent_version": "1.0.0"
        }

    # 1. Write to ProgramData
    try:
        os.makedirs(pd_dir, exist_ok=True)
        with open(pd_config, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Persisted assigned server configuration to: {pd_config}")
    except Exception as e:
        logger.warning(f"Could not write to ProgramData config: {e}")

    # 2. Write to AppData as user-level backup
    appdata = os.environ.get("APPDATA")
    if appdata:
        user_cfg_dir = os.path.join(appdata, "RetroVault", "agent")
        try:
            os.makedirs(user_cfg_dir, exist_ok=True)
            with open(os.path.join(user_cfg_dir, "config.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass


def ensure_startup_persistence(source_config_path: Optional[str] = None) -> bool:
    """
    Register the agent executable in Windows Startup Apps.
    This guarantees that when the Windows laptop restarts or shuts down and opens again,
    the agent launches automatically in the background without user consent.
    """
    logger = get_logger()

    # 1. Permanently preserve server configuration
    persist_config_file(source_config_path)

    if sys.platform != "win32" and not WINREG_AVAILABLE:
        logger.debug("Startup persistence skipped: non-Windows environment.")
        return False

    success = False
    exe_target = get_current_executable()
    # Format run command: e.g. "C:\Path\RetroVaultAgent.exe" --run
    if getattr(sys, "frozen", False):
        run_command = f'"{exe_target}" --run'
    else:
        run_command = f'{exe_target} --run'

    # Method A: Windows Registry Run Key for Current User (no UAC required!)
    if WINREG_AVAILABLE:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                STARTUP_REG_KEY,
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, run_command)
            winreg.CloseKey(key)
            logger.info(f"Windows Startup App registered in HKCU: {run_command}")
            success = True
        except Exception as e:
            logger.warning(f"Could not register in HKCU Run registry: {e}")

        # If running as administrator, also write to HKLM for system-wide startup
        try:
            key_lm = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                STARTUP_REG_KEY,
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key_lm, APP_NAME, 0, winreg.REG_SZ, run_command)
            winreg.CloseKey(key_lm)
            logger.info(f"Windows Startup App registered in HKLM: {run_command}")
            success = True
        except Exception:
            # Expected for standard user without admin rights; HKCU handles it
            pass

    # Method B: Startup Folder launcher script (dual redundancy)
    try:
        startup_dir = get_user_startup_folder()
        if startup_dir:
            launcher_cmd = os.path.join(startup_dir, "RetroVaultAgent.cmd")
            with open(launcher_cmd, "w", encoding="utf-8") as f:
                f.write("@echo off\r\n")
                f.write(f'start "" /B {run_command}\r\n')
            logger.info(f"Windows Startup launcher written to: {launcher_cmd}")
            success = True
    except Exception as e:
        logger.warning(f"Could not create Startup folder script: {e}")

    return success


def remove_startup_persistence() -> bool:
    """Remove agent from Windows Startup Apps."""
    logger = get_logger()
    removed = False

    if WINREG_AVAILABLE:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                STARTUP_REG_KEY,
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
            logger.info("Removed RetroVaultAgent from HKCU Startup registry.")
            removed = True
        except Exception:
            pass

    try:
        startup_dir = get_user_startup_folder()
        if startup_dir:
            launcher_cmd = os.path.join(startup_dir, "RetroVaultAgent.cmd")
            if os.path.exists(launcher_cmd):
                os.remove(launcher_cmd)
                logger.info("Removed RetroVaultAgent from Startup folder.")
                removed = True
    except Exception:
        pass

    return removed

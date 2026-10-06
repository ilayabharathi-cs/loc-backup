"""Build script to compile RetroVault Universal Agent into a standalone Windows .exe using PyInstaller."""

import os
import sys
import subprocess
import shutil

def build_windows_exe():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    agent_dir = os.path.join(project_root, "agent")
    entrypoint = os.path.join(agent_dir, "src", "main.py")
    dist_dir = os.path.join(agent_dir, "dist")
    build_dir = os.path.join(agent_dir, "build")

    print("=" * 60)
    print(" RetroVault Agent - Windows Standalone Executable Builder")
    print("=" * 60)

    # 1. Verify entry point exists
    if not os.path.exists(entrypoint):
        print(f"[-] Entrypoint not found: {entrypoint}")
        sys.exit(1)

    # 2. Check if pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("[*] PyInstaller not installed in current Python environment.")
        print("[*] Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "pydantic>=2.7.0"])

    # 3. Build command
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name=RetroVaultAgent",
        "--onefile",
        "--clean",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--paths={project_root}",
        f"--paths={agent_dir}",
        # Hidden imports needed for pydantic and agent components
        "--hidden-import=pydantic",
        "--hidden-import=pydantic.deprecated.decorator",
        "--hidden-import=agent.src.backup.backup_engine",
        "--hidden-import=agent.src.backup.live_sync",
        "--hidden-import=agent.src.windows.startup",
        "--hidden-import=agent.src.user_discovery",
        "--hidden-import=agent.src.path_resolver",
        "--hidden-import=agent.src.system_info",
        "--hidden-import=agent.src.service",
        "--hidden-import=agent.src.scheduler",
        "--hidden-import=agent.src.restore",
        "--hidden-import=agent.native.python.native_bridge",
        f"--add-data={os.path.join(agent_dir, 'native', 'bin', 'retrovault_native.dll')};agent/native/bin",
        entrypoint
    ]

    print(f"[*] Running PyInstaller command:\n{' '.join(cmd)}\n")
    ret = subprocess.call(cmd)

    if ret == 0:
        exe_path = os.path.join(dist_dir, "RetroVaultAgent.exe")
        print("\n" + "=" * 60)
        print(f"[+] Build SUCCESSFUL!")
        print(f"[+] Output executable: {exe_path}")
        print("=" * 60)
    else:
        print(f"\n[-] Build failed with exit code: {ret}")
        sys.exit(ret)

if __name__ == "__main__":
    build_windows_exe()

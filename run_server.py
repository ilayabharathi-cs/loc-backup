import os
import sys
import subprocess
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent
    server_dir = root / "server"
    
    # Check for venv python / uvicorn
    venv_dir = server_dir / ".venv"
    if os.name == "nt":
        venv_uvicorn = venv_dir / "Scripts" / "uvicorn.exe"
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_uvicorn = venv_dir / "bin" / "uvicorn"
        venv_python = venv_dir / "bin" / "python3"
    
    if venv_uvicorn.exists():
        cmd = [str(venv_uvicorn)]
    elif venv_python.exists():
        cmd = [str(venv_python), "-m", "uvicorn"]
    else:
        cmd = [sys.executable, "-m", "uvicorn"]
    
    cmd.extend([
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--app-dir", "server",
        "--reload"
    ])
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(server_dir)
    
    print(f"Starting RetroVault Control Plane API server on http://localhost:8000 ...")
    try:
        subprocess.run(cmd, env=env, cwd=str(root))
    except KeyboardInterrupt:
        print("\nStopping server.")

if __name__ == "__main__":
    main()

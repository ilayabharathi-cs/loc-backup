#!/usr/bin/env bash
# ==============================================================================
# RetroVault Server Launcher for Linux
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "====================================================================="
echo "       Starting RetroVault Backup Control Plane Server"
echo "====================================================================="
echo ""

# 1. Detect Python 3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3 was not found! Please install python3 (e.g. sudo apt install python3 python3-pip python3-venv)"
    exit 1
fi

echo "[OK] Python detected: $($PYTHON_BIN --version)"

# 2. Check / Create Virtual Environment (recommended for Linux)
VENV_DIR="$SCRIPT_DIR/server/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[*] Setting up Python virtual environment in server/.venv ..."
    $PYTHON_BIN -m venv "$VENV_DIR" || {
        echo "[WARNING] Could not create virtual environment. Using system Python directly."
    }
fi

if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    PYTHON_BIN="python"
fi

# 3. Check / Install Server Dependencies
if ! $PYTHON_BIN -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "[*] Installing server dependencies from server/requirements.txt ..."
    $PYTHON_BIN -m pip install -r "$SCRIPT_DIR/server/requirements.txt"
fi

# 4. Launch Server
echo ""
echo "====================================================================="
echo "Server starting on: http://0.0.0.0:8000"
echo "API Docs available at: http://localhost:8000/docs"
echo "Press Ctrl+C to stop."
echo "====================================================================="
echo ""

exec $PYTHON_BIN "$SCRIPT_DIR/run_server.py"

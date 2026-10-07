#!/usr/bin/env bash
# ==============================================================================
# RetroVault Universal Linux Client Agent Launcher
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "====================================================================="
echo "          RetroVault Universal Linux Backup Agent"
echo "====================================================================="
echo ""

# 1. Detect Python 3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3 was not found! Please install python3 (e.g. sudo apt install python3 python3-pip)"
    exit 1
fi

echo "[OK] Python detected: $($PYTHON_BIN --version)"

# 2. Check dependencies (pydantic)
if ! $PYTHON_BIN -c "import pydantic" >/dev/null 2>&1; then
    echo "[*] Installing required pydantic library..."
    $PYTHON_BIN -m pip install pydantic || pip3 install pydantic
fi

# 3. Check config.json
CONFIG_FILE="$SCRIPT_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[*] Creating default config.json..."
    cat <<EOF > "$CONFIG_FILE"
{
  "server_url": "http://127.0.0.1:8000",
  "heartbeat_interval_seconds": 30,
  "log_level": "INFO",
  "agent_version": "1.0.0"
}
EOF
fi

SERVER_URL=$($PYTHON_BIN -c "import json; cfg=json.load(open('$CONFIG_FILE')); print(cfg.get('server_url', 'http://127.0.0.1:8000'))")
echo "[OK] Configured Server URL: $SERVER_URL"

# 4. Test connectivity to Server
echo ""
echo "---------------------------------------------------------------------"
echo "Testing connection to RetroVault Backup Server ($SERVER_URL)..."
echo "---------------------------------------------------------------------"

if $PYTHON_BIN -c "import urllib.request, sys; res=urllib.request.urlopen('$SERVER_URL/health', timeout=5); sys.stdout.write('[OK] Connected! Server: ' + res.read().decode() + '\n')"; then
    echo ""
    echo "====================================================================="
    echo "Connected! Starting RetroVault Universal Agent..."
    echo "Press Ctrl+C anytime in this window to stop."
    echo "====================================================================="
    echo ""
else
    echo ""
    echo "[WARNING] Could not connect to $SERVER_URL/health"
    echo "Please verify:"
    echo "  1. The server is running and accessible over network"
    echo "  2. Firewall allows port 8000"
    echo ""
    read -p "Start agent anyway and retry in background? (y/N): " RETRY
    if [[ ! "$RETRY" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 5. Launch Agent
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
exec $PYTHON_BIN "$SCRIPT_DIR/src/main.py" --run --config "$CONFIG_FILE"

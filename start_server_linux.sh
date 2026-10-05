#!/bin/bash

echo "====================================================================="
echo "           RetroVault Backup Server - Control Plane"
echo "====================================================================="
echo

# Move to the directory where this script is located
cd "$(dirname "$0")" || exit 1

# 1. Detect Python
if [ -x ".venv/bin/python" ]; then
    PYTHON_EXE=".venv/bin/python"
elif [ -x "server/.venv/bin/python" ]; then
    PYTHON_EXE="server/.venv/bin/python"
else
    PYTHON_EXE="python3"
fi

echo "[OK] Python: $PYTHON_EXE"
echo

# 2. Show local network IP addresses
echo "Detecting Local Network IP Addresses for Client Agents..."
echo

hostname -I | tr ' ' '\n' | while read -r IP; do
    if [ -n "$IP" ]; then
        echo "  [+] Host IP: $IP"
    fi
done

echo
echo "Client agents should point their server_url to one of the above IPs on port 8000"
echo "Example: http://192.168.0.131:8000"
echo

echo "---------------------------------------------------------------------"
echo "Starting RetroVault Server on 0.0.0.0:8000..."
echo "---------------------------------------------------------------------"
echo

"$PYTHON_EXE" run_server.py

echo
echo "RetroVault server stopped."

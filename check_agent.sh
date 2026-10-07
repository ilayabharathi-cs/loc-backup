#!/usr/bin/env bash
# ==============================================================================
# RetroVault Universal Linux Client Agent - Status Check
# ==============================================================================

# Terminal Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}          RetroVault Universal Client Agent - Status Check           ${NC}"
echo -e "${CYAN}=====================================================================${NC}"
echo ""

AGENT_RUNNING=0
RUN_TYPE=""
RUN_DETAILS=""

# Resolve Directories (works whether run from project root or agent/ directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SCRIPT_DIR/agent/src" ]; then
    PROJECT_ROOT="$SCRIPT_DIR"
    AGENT_DIR="$SCRIPT_DIR/agent"
elif [ -d "$SCRIPT_DIR/src" ]; then
    AGENT_DIR="$SCRIPT_DIR"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
else
    PROJECT_ROOT="$SCRIPT_DIR"
    AGENT_DIR="$SCRIPT_DIR/agent"
fi

# 1. Check Systemd Service (retrovault-agent)
SERVICE_NAME="retrovault-agent"
if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        AGENT_RUNNING=1
        RUN_TYPE="Systemd Service"
        RUN_DETAILS="Unit: $SERVICE_NAME (active/running)"
        echo -e "${GREEN}[OK] Systemd Service detected:${NC} $SERVICE_NAME is RUNNING."
    elif systemctl list-unit-files "$SERVICE_NAME.service" >/dev/null 2>&1; then
        SVC_STATUS=$(systemctl is-active "$SERVICE_NAME" 2>/dev/null || echo "inactive")
        echo -e "${YELLOW}[INFO] Systemd Service $SERVICE_NAME is installed but status is: $SVC_STATUS${NC}"
    else
        echo -e "${GRAY}[INFO] Systemd Service '$SERVICE_NAME' is not installed.${NC}"
    fi
else
    echo -e "${GRAY}[INFO] systemctl not available on this system.${NC}"
fi

# 2. Check Running Process (Python Daemon or Executable)
PID_LIST=$(pgrep -f "main\.py.*--run|agent\.main.*--run|retrovault-agent" 2>/dev/null | grep -v "$$" || true)

if [ -n "$PID_LIST" ]; then
    AGENT_RUNNING=1
    if [ -z "$RUN_TYPE" ]; then
        RUN_TYPE="Background Process"
        RUN_DETAILS="PID: $(echo $PID_LIST | tr '\n' ' ')"
    fi
    for PID in $PID_LIST; do
        if [ -d "/proc/$PID" ]; then
            CMDLINE=$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null || ps -p "$PID" -o args= 2>/dev/null)
            echo -e "${GREEN}[OK] Active Process Found:${NC} PID $PID"
            echo -e "     ${GRAY}Command: $CMDLINE${NC}"
        fi
    done
fi

echo ""
echo -e "${CYAN}---------------------------------------------------------------------${NC}"
echo -e "${CYAN}Configuration and Identity Details:${NC}"
echo -e "${CYAN}---------------------------------------------------------------------${NC}"

# 3. Detect Configuration File
FOUND_CONFIG=""
if [ -f "/etc/retrovault/config.json" ]; then
    FOUND_CONFIG="/etc/retrovault/config.json"
elif [ -f "$AGENT_DIR/config.json" ]; then
    FOUND_CONFIG="$AGENT_DIR/config.json"
elif [ -f "$HOME/.config/retrovault/config.json" ]; then
    FOUND_CONFIG="$HOME/.config/retrovault/config.json"
elif [ -f "$PROJECT_ROOT/config.json" ]; then
    FOUND_CONFIG="$PROJECT_ROOT/config.json"
fi

if [ -n "$FOUND_CONFIG" ] && [ -f "$FOUND_CONFIG" ]; then
    echo -e "  [+] Config File: $FOUND_CONFIG"
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "
import json
try:
    with open('$FOUND_CONFIG') as f:
        d = json.load(f)
    print(f\"      Server URL: {d.get('server_url', 'N/A')}\")
    print(f\"      Heartbeat Interval: {d.get('heartbeat_interval_seconds', 'N/A')}s\")
    print(f\"      Agent Version: {d.get('agent_version', 'N/A')}\")
except Exception as e:
    print(f'      Error reading config: {e}')
" 2>/dev/null
    else
        grep -E '"server_url"|"heartbeat_interval_seconds"|"agent_version"' "$FOUND_CONFIG" | sed 's/^/      /'
    fi
else
    echo -e "  [-] Config File: Not found (default config created on startup)"
fi

# 4. Detect Identity File
FOUND_IDENTITY=""
if [ -f "/var/lib/retrovault/agent/identity.json" ]; then
    FOUND_IDENTITY="/var/lib/retrovault/agent/identity.json"
elif [ -f "$AGENT_DIR/identity.json" ]; then
    FOUND_IDENTITY="$AGENT_DIR/identity.json"
elif [ -f "$HOME/.local/share/retrovault/agent/identity.json" ]; then
    FOUND_IDENTITY="$HOME/.local/share/retrovault/agent/identity.json"
fi

if [ -n "$FOUND_IDENTITY" ] && [ -f "$FOUND_IDENTITY" ]; then
    echo -e "  [+] Identity File: $FOUND_IDENTITY"
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "
import json
try:
    with open('$FOUND_IDENTITY') as f:
        d = json.load(f)
    print(f\"      Device ID: {d.get('device_id', 'N/A')}\")
    cid = d.get('client_id')
    if cid:
        print(f\"      Client ID: {cid} \033[0;32m[Enrolled]\033[0m\")
    else:
        print(\"      Client ID: \033[1;33mNot Enrolled Yet\033[0m\")
except Exception as e:
    print(f'      Error reading identity: {e}')
" 2>/dev/null
    fi
else
    echo -e "  [-] Identity File: Not created yet (will be generated on first run)"
fi

# 5. Check Log File
FOUND_LOG=""
if [ -f "/var/log/retrovault/agent.log" ]; then
    FOUND_LOG="/var/log/retrovault/agent.log"
elif [ -f "$AGENT_DIR/logs/agent.log" ]; then
    FOUND_LOG="$AGENT_DIR/logs/agent.log"
fi

if [ -n "$FOUND_LOG" ] && [ -f "$FOUND_LOG" ]; then
    echo ""
    echo -e "${CYAN}---------------------------------------------------------------------${NC}"
    echo -e "${CYAN}Recent Agent Logs (Last 5 lines from $FOUND_LOG):${NC}"
    echo -e "${CYAN}---------------------------------------------------------------------${NC}"
    tail -n 5 "$FOUND_LOG" 2>/dev/null | sed "s/^/  ${GRAY}/" | sed "s/$/${NC}/"
fi

echo ""
echo -e "${CYAN}=====================================================================${NC}"
if [ "$AGENT_RUNNING" -eq 1 ]; then
    echo -e "${GREEN}[RUNNING] RetroVault Agent is ACTIVE and RUNNING!${NC}"
    echo -e "Type: $RUN_TYPE ($RUN_DETAILS)"
    echo -e "${CYAN}=====================================================================${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}[STOPPED] RetroVault Agent is NOT running.${NC}"
    echo ""
    echo "To start the agent:"
    echo "  - Foreground: ./start_agent.sh (or cd agent && ./start_agent.sh)"
    echo "  - Systemd Service: sudo systemctl start retrovault-agent"
    echo -e "${CYAN}=====================================================================${NC}"
    echo ""
    exit 1
fi

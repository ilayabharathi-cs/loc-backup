#!/usr/bin/env bash
# ==============================================================================
# RetroVault Universal Linux Client Agent - Complete Uninstaller & Cleaner
# ==============================================================================

set -u

# Terminal Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
GRAY='\033[0;90m'
NC='\033[0m'

echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}   RetroVault Universal Linux Client Agent - Complete Uninstaller    ${NC}"
echo -e "${CYAN}=====================================================================${NC}"
echo ""

FORCE=0
for arg in "$@"; do
    if [ "$arg" == "--force" ] || [ "$arg" == "-f" ]; then
        FORCE=1
    fi
done

# Confirmation prompt
if [ "$FORCE" -eq 0 ]; then
    echo -e "${YELLOW}WARNING: This action will:${NC}"
    echo "  1. Kill all running agent background processes."
    echo "  2. Stop, disable, and delete the systemd service (retrovault-agent)."
    echo "  3. Remove autostart and cron persistence."
    echo "  4. Delete all agent directories (/opt/retrovault, /etc/retrovault, etc.)."
    echo "  5. Remove dedicated system user 'retrovault'."
    echo ""
    read -r -p "Are you sure you want to completely uninstall the agent? (y/N): " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo -e "${GRAY}[INFO] Uninstallation cancelled by user.${NC}"
        exit 0
    fi
fi

# Resolve Directories
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

IS_ROOT=0
if [ "$(id -u)" -eq 0 ]; then
    IS_ROOT=1
fi

SUDO_CMD=""
if [ "$IS_ROOT" -eq 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO_CMD="sudo"
    fi
fi

echo ""
echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}[*] Phase 1: Terminating all Agent Background Processes...           ${NC}"
echo -e "${CYAN}=====================================================================${NC}"

# Find and kill processes
AGENT_PIDS=$(pgrep -f "main\.py.*--run|agent\.main.*--run|retrovault-agent" 2>/dev/null | grep -v "$$" || true)

if [ -n "$AGENT_PIDS" ]; then
    for PID in $AGENT_PIDS; do
        echo -e "  [+] Sending SIGTERM to Process PID: ${YELLOW}$PID${NC}"
        kill -15 "$PID" 2>/dev/null || true
    done
    sleep 1

    # Force kill any lingering processes with SIGKILL (-9)
    REMAINING=$(pgrep -f "main\.py.*--run|agent\.main.*--run|retrovault-agent" 2>/dev/null | grep -v "$$" || true)
    if [ -n "$REMAINING" ]; then
        for PID in $REMAINING; do
            echo -e "  [+] Force killing (SIGKILL) lingering Process PID: ${RED}$PID${NC}"
            kill -9 "$PID" 2>/dev/null || true
        done
        sleep 1
    fi
    echo -e "  ${GREEN}[OK] Terminated all agent background processes.${NC}"
else
    echo -e "  ${GREEN}[OK] No active agent background processes found.${NC}"
fi

echo ""
echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}[*] Phase 2: Stopping & Removing Systemd Service...                  ${NC}"
echo -e "${CYAN}=====================================================================${NC}"

SERVICE_NAME="retrovault-agent"
if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo "  [*] Stopping systemd service $SERVICE_NAME..."
        $SUDO_CMD systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    fi

    if systemctl list-unit-files "$SERVICE_NAME.service" >/dev/null 2>&1; then
        echo "  [*] Disabling systemd service $SERVICE_NAME..."
        $SUDO_CMD systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    fi

    # Remove unit files
    if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
        $SUDO_CMD rm -f "/etc/systemd/system/$SERVICE_NAME.service"
        echo "  [OK] Removed /etc/systemd/system/$SERVICE_NAME.service"
    fi
    if [ -f "/lib/systemd/system/$SERVICE_NAME.service" ]; then
        $SUDO_CMD rm -f "/lib/systemd/system/$SERVICE_NAME.service"
        echo "  [OK] Removed /lib/systemd/system/$SERVICE_NAME.service"
    fi

    $SUDO_CMD systemctl daemon-reload 2>/dev/null || true
    $SUDO_CMD systemctl reset-failed 2>/dev/null || true
    echo -e "  ${GREEN}[OK] Systemd service removed and daemon reloaded.${NC}"
else
    echo -e "  ${GRAY}[INFO] systemctl not found on this system.${NC}"
fi

echo ""
echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}[*] Phase 3: Removing Autostart & Cron Persistence...                ${NC}"
echo -e "${CYAN}=====================================================================${NC}"

# Remove XDG autostart desktop entry
if [ -f "$HOME/.config/autostart/retrovault-agent.desktop" ]; then
    rm -f "$HOME/.config/autostart/retrovault-agent.desktop"
    echo "  [OK] Removed user autostart desktop entry."
fi
if [ -f "/etc/xdg/autostart/retrovault-agent.desktop" ]; then
    $SUDO_CMD rm -f "/etc/xdg/autostart/retrovault-agent.desktop"
    echo "  [OK] Removed system autostart desktop entry."
fi

# Clean crontab entries if any mention retrovault
if command -v crontab >/dev/null 2>&1; then
    if crontab -l 2>/dev/null | grep -q "retrovault"; then
        crontab -l 2>/dev/null | grep -v "retrovault" | crontab - 2>/dev/null || true
        echo "  [OK] Removed retrovault schedule from user crontab."
    fi
fi

echo ""
echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}[*] Phase 4: Cleaning Up Data, Configuration, Cache & Logs...        ${NC}"
echo -e "${CYAN}=====================================================================${NC}"

PATHS_TO_REMOVE=(
    "/opt/retrovault"
    "/etc/retrovault"
    "/var/lib/retrovault"
    "/var/log/retrovault"
    "/run/retrovault"
    "$HOME/.config/retrovault"
    "$HOME/.local/share/retrovault"
    "$AGENT_DIR/logs"
    "$AGENT_DIR/locks"
    "$PROJECT_ROOT/logs"
    "$PROJECT_ROOT/locks"
)

for TARGET in "${PATHS_TO_REMOVE[@]}"; do
    if [ -e "$TARGET" ]; then
        if [ "$IS_ROOT" -eq 1 ] || [ -w "$(dirname "$TARGET")" ]; then
            rm -rf "$TARGET" 2>/dev/null || true
        else
            $SUDO_CMD rm -rf "$TARGET" 2>/dev/null || true
        fi
        echo "  [OK] Removed: $TARGET"
    fi
done

echo ""
echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}[*] Phase 5: Removing Dedicated Service User (if exists)...          ${NC}"
echo -e "${CYAN}=====================================================================${NC}"

if id -u retrovault >/dev/null 2>&1; then
    echo "  [*] Removing system user 'retrovault'..."
    $SUDO_CMD userdel -r retrovault 2>/dev/null || $SUDO_CMD userdel retrovault 2>/dev/null || true
    echo "  [OK] Removed system user 'retrovault'."
else
    echo "  [OK] System user 'retrovault' does not exist."
fi

echo ""
echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}[*] Phase 6: Verification Check...                                   ${NC}"
echo -e "${CYAN}=====================================================================${NC}"

FINAL_CHECK_PIDS=$(pgrep -f "main\.py.*--run|agent\.main.*--run|retrovault-agent" 2>/dev/null | grep -v "$$" || true)

if [ -z "$FINAL_CHECK_PIDS" ]; then
    echo -e "  ${GREEN}[OK] Zero agent processes running.${NC}"
else
    echo -e "  ${RED}[WARNING] Process PID $FINAL_CHECK_PIDS still active.${NC}"
fi

if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo -e "  ${RED}[WARNING] Systemd service $SERVICE_NAME is still active.${NC}"
    else
        echo -e "  ${GREEN}[OK] Systemd service is stopped and removed.${NC}"
    fi
fi

echo ""
echo -e "${CYAN}=====================================================================${NC}"
echo -e "${GREEN}[SUCCESS] RetroVault Client Agent has been COMPLETELY REMOVED!       ${NC}"
echo "  - All background processes killed"
echo "  - Systemd service stopped and uninstalled"
echo "  - Autostart and cron persistence removed"
echo "  - Data directories, configuration, logs, and state deleted"
echo -e "${CYAN}=====================================================================${NC}"
echo ""

exit 0

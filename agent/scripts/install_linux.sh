#!/usr/bin/env bash
# ==============================================================================
# RetroVault Lightweight Linux Agent Installer
# Creates dedicated unprivileged service user, directories, installs systemd unit
# ==============================================================================

set -euo pipefail

echo "===> Installing RetroVault Lightweight Linux Agent..."

# Ensure root privileges for installation
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo ./install_linux.sh)" >&2
    exit 1
fi

# 1. Create dedicated system user with minimal privileges
if ! id -u retrovault >/dev/null 2>&1; then
    echo "Creating system user 'retrovault'..."
    useradd --system --no-create-home --shell /usr/sbin/nologin retrovault
fi

# 2. Setup standard FHS directories
echo "Configuring standard FHS directories..."
mkdir -p /opt/retrovault
mkdir -p /etc/retrovault
mkdir -p /var/lib/retrovault/agent
mkdir -p /var/log/retrovault
mkdir -p /run/retrovault

# Permissions
chown -R retrovault:retrovault /opt/retrovault
chown -R retrovault:retrovault /var/lib/retrovault
chown -R retrovault:retrovault /var/log/retrovault
chown -R retrovault:retrovault /run/retrovault
chmod 750 /var/lib/retrovault/agent
chmod 755 /etc/retrovault

# 3. Copy service unit
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/retrovault-agent.service" ]; then
    echo "Installing systemd service unit..."
    cp "$SCRIPT_DIR/retrovault-agent.service" /etc/systemd/system/retrovault-agent.service
    systemctl daemon-reload
    systemctl enable retrovault-agent.service
    echo "Service enabled. Start with: sudo systemctl start retrovault-agent"
fi

echo "===> RetroVault Linux Agent installation complete."

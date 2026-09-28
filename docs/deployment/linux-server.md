# RetroVault Local Backup Server — Linux Deployment Guide

This guide describes deploying the **RetroVault Local Backup Server** on Linux (Ubuntu / Debian / RHEL / Rocky Linux) as a production system service backed by PostgreSQL and local Content Addressable Storage (CAS).

---

## 1. Prerequisites

- **Supported Linux Distributions**: Ubuntu 22.04/24.04 LTS, Debian 12, RHEL/Rocky 9+
- **Python**: Python 3.10, 3.11, or 3.12 (`python3`, `python3-venv`, `python3-pip`)
- **PostgreSQL**: PostgreSQL 14, 15, or 16
- **System Memory**: Minimum 2 GB RAM (4 GB recommended)
- **Dedicated Storage**: Local mounted volume or directory for CAS repository (e.g. `/data/retrovault/repository` or `/var/lib/retrovault/repository`)

---

## 2. Dedicated System User & Directory Setup

Create a dedicated non-privileged service user and initialize directory structures:

```bash
# Create dedicated system user
sudo useradd -r -s /bin/false -d /var/lib/retrovault -m retrovault

# Create application directories
sudo mkdir -p /opt/retrovault/server
sudo mkdir -p /etc/retrovault
sudo mkdir -p /var/log/retrovault
sudo mkdir -p /data/retrovault/repository

# Set directory permissions
sudo chown -R retrovault:retrovault /var/lib/retrovault
sudo chown -R retrovault:retrovault /var/log/retrovault
sudo chown -R retrovault:retrovault /data/retrovault/repository
sudo chmod 750 /data/retrovault/repository
```

---

## 3. PostgreSQL Database Setup

```bash
# Connect to PostgreSQL as superuser
sudo -u postgres psql

# Execute SQL commands:
CREATE USER retrovault_user WITH PASSWORD 'YourSecureDbPasswordHere';
CREATE DATABASE retrovault_db OWNER retrovault_user;
GRANT ALL PRIVILEGES ON DATABASE retrovault_db TO retrovault_user;
\q
```

---

## 4. Application Installation & Python Runtime

```bash
# Copy server files into /opt/retrovault/server
sudo cp -r /path/to/source/server/* /opt/retrovault/server/
cd /opt/retrovault/server

# Create virtual environment
sudo python3 -m venv /opt/retrovault/venv
sudo /opt/retrovault/venv/bin/pip install --upgrade pip
sudo /opt/retrovault/venv/bin/pip install -r /opt/retrovault/server/requirements.txt

# Set ownership
sudo chown -R retrovault:retrovault /opt/retrovault
```

---

## 5. Production Configuration

Create the environment file `/etc/retrovault/server.env` (accessible only by `retrovault` user):

```ini
# /etc/retrovault/server.env
ENVIRONMENT=production
DEBUG=False
PROJECT_NAME="RetroVault Local Backup Control Plane"

# Network
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=postgresql://retrovault_user:YourSecureDbPasswordHere@127.0.0.1:5432/retrovault_db

# Security & Secrets
SECRET_KEY=generate_a_random_64_char_secret_key_here
JWT_SECRET_KEY=generate_a_random_64_char_jwt_secret_key_here

# Local CAS Repository Root
RETROVAULT_REPOSITORY_PATH=/data/retrovault/repository

# Logging & Temp
LOG_PATH=/var/log/retrovault
TEMP_PATH=/tmp

# CORS (specify administrative web console origins)
CORS_ORIGINS=["https://backup-admin.internal.company.com"]
```

Secure the environment file:
```bash
sudo chown root:retrovault /etc/retrovault/server.env
sudo chmod 640 /etc/retrovault/server.env
```

---

## 6. Systemd Service Configuration

Create `/etc/systemd/system/retrovault-server.service`:

```ini
[Unit]
Description=RetroVault Local Backup Server
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=retrovault
Group=retrovault
WorkingDirectory=/opt/retrovault/server
EnvironmentFile=/etc/retrovault/server.env
ExecStart=/opt/retrovault/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info

# Hardening & Sandboxing
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/data/retrovault/repository /var/log/retrovault /var/lib/retrovault /tmp
PrivateTmp=true
NoNewPrivileges=true
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable retrovault-server
sudo systemctl start retrovault-server
sudo systemctl status retrovault-server
```

---

## 7. Reverse Proxy & TLS Configuration (Nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name backup-server.internal.company.com;

    ssl_certificate /etc/ssl/certs/retrovault.crt;
    ssl_certificate_key /etc/ssl/private/retrovault.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

---

## 8. Verification

```bash
# Verify Health Endpoint
curl -k https://127.0.0.1:8000/health

# Expected response:
# {"status":"ok","database":"connected","product":"RetroVault Local Backup","version":"1.0.0","server_platform":"Linux","server_os_release":"...","database_engine":"postgresql","repository_root":"/data/retrovault/repository"}
```

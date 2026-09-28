# RetroVault Local Backup Server — Windows Server Deployment Guide

This guide describes deploying the **RetroVault Local Backup Server** on Windows Server (2019 / 2022 / 2025) as a background Windows Service backed by PostgreSQL for Windows and local Content Addressable Storage (CAS).

---

## 1. Prerequisites

- **Supported OS**: Windows Server 2019, 2022, 2025 (Standard / Datacenter)
- **Python**: Python 3.10, 3.11, or 3.12 (64-bit) installed for all users
- **PostgreSQL**: PostgreSQL 14, 15, or 16 for Windows
- **Service Manager**: Windows Service Wrapper (e.g. WinSW or NSSM) or Python Win32 Service
- **Storage Volume**: Dedicated NTFS / ReFS volume or directory for CAS repository (e.g. `D:\RetroVault\Repository` or `E:\BackupStore\CAS`)

---

## 2. Dedicated Service Account & Directory Setup

In PowerShell (Run as Administrator):

```powershell
# Create dedicated local service account (or Managed Service Account in AD)
$Password = ConvertTo-SecureString "YourSecureSvcPasswordHere123!" -AsPlainText -Force
New-LocalUser -Name "svc_retrovault" -Password $Password -Description "Service Account for RetroVault Backup Server" -PasswordNeverExpires

# Create installation & storage directories
New-Item -ItemType Directory -Force -Path "C:\Program Files\RetroVault\Server"
New-Item -ItemType Directory -Force -Path "C:\ProgramData\RetroVault\Config"
New-Item -ItemType Directory -Force -Path "C:\ProgramData\RetroVault\Logs"
New-Item -ItemType Directory -Force -Path "D:\RetroVault\Repository"

# Grant NTFS permissions to svc_retrovault
$Acl = Get-Acl "D:\RetroVault\Repository"
$Rule = New-Object System.Security.AccessControl.FileSystemAccessRule("svc_retrovault","FullControl","ContainerInherit,ObjectInherit","None","Allow")
$Acl.SetAccessRule($Rule)
Set-Acl "D:\RetroVault\Repository" $Acl
```

---

## 3. PostgreSQL Database Setup

Open `psql` command line or pgAdmin:

```sql
CREATE USER retrovault_user WITH PASSWORD 'YourSecureDbPasswordHere';
CREATE DATABASE retrovault_db OWNER retrovault_user;
GRANT ALL PRIVILEGES ON DATABASE retrovault_db TO retrovault_user;
```

---

## 4. Application Installation & Python Runtime

```powershell
# Copy server files into Program Files
Copy-Item -Recurse -Force ".\server\*" "C:\Program Files\RetroVault\Server\"

# Create dedicated virtual environment
cd "C:\Program Files\RetroVault\Server"
python -m venv "C:\Program Files\RetroVault\Server\.venv"
& "C:\Program Files\RetroVault\Server\.venv\Scripts\pip.exe" install --upgrade pip
& "C:\Program Files\RetroVault\Server\.venv\Scripts\pip.exe" install -r "C:\Program Files\RetroVault\Server\requirements.txt"
```

---

## 5. Production Configuration

Create the environment file `C:\ProgramData\RetroVault\Config\server.env`:

```ini
# C:\ProgramData\RetroVault\Config\server.env
ENVIRONMENT=production
DEBUG=False
PROJECT_NAME="RetroVault Local Backup Control Plane"

# Networking
HOST=0.0.0.0
PORT=8000

# PostgreSQL Connection
DATABASE_URL=postgresql://retrovault_user:YourSecureDbPasswordHere@127.0.0.1:5432/retrovault_db

# Security & Keys
SECRET_KEY=generate_a_random_64_char_secret_key_here
JWT_SECRET_KEY=generate_a_random_64_char_jwt_secret_key_here

# Local CAS Repository Root
RETROVAULT_REPOSITORY_PATH=D:\RetroVault\Repository

# Logging & Temp
LOG_PATH=C:\ProgramData\RetroVault\Logs
TEMP_PATH=C:\ProgramData\RetroVault\Temp

# CORS Origins
CORS_ORIGINS=["https://backup-admin.internal.company.com"]
```

---

## 6. Windows Service Installation (Using WinSW or NSSM)

Using WinSW:
Create `C:\Program Files\RetroVault\Server\retrovault-server.xml`:

```xml
<service>
  <id>RetroVaultServer</id>
  <name>RetroVault Local Backup Server</name>
  <description>Core control plane, metadata database manager, and CAS repository service for RetroVault Backup.</description>
  <executable>C:\Program Files\RetroVault\Server\.venv\Scripts\python.exe</executable>
  <arguments>-m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info</arguments>
  <workingdirectory>C:\Program Files\RetroVault\Server</workingdirectory>
  <env name="RETROVAULT_CONFIG_FILE" value="C:\ProgramData\RetroVault\Config\server.env" />
  <logpath>C:\ProgramData\RetroVault\Logs</logpath>
  <log mode="roll-by-size">
    <sizeThreshold>10240</sizeThreshold>
    <keepFiles>8</keepFiles>
  </log>
  <serviceaccount>
    <username>.\svc_retrovault</username>
    <password>YourSecureSvcPasswordHere123!</password>
  </serviceaccount>
  <onfailure action="restart" delay="5 sec" />
</service>
```

Install and start the service:
```powershell
# Install service
& "C:\Program Files\RetroVault\Server\WinSW.exe" install "C:\Program Files\RetroVault\Server\retrovault-server.xml"

# Start service
Start-Service -Name "RetroVaultServer"
Get-Service -Name "RetroVaultServer"
```

---

## 7. Windows Firewall Configuration

```powershell
# Open inbound port 8000 for client backups
New-NetFirewallRule -DisplayName "RetroVault Backup Server (HTTP/REST)" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

---

## 8. Verification

```powershell
# Verify Server Health Endpoint via PowerShell
$response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get
$response | Format-List

# Expected Output:
# status          : ok
# database        : connected
# product         : RetroVault Local Backup
# version         : 1.0.0
# server_platform : Windows
# server_os_release: 10.0.20348
# database_engine : postgresql
# repository_root : D:\RetroVault\Repository
```

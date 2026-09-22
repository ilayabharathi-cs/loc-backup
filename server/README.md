# RetroVault Backup — Control Plane Backend & Database

Enterprise Control Plane REST API and PostgreSQL database foundation for the RetroVault Backup Management System.

## Technology Stack

- **Framework**: Python 3.12+ / FastAPI
- **ASGI Server**: Uvicorn
- **Database**: PostgreSQL (SQLAlchemy 2.0 ORM + Alembic migrations)
- **Validation**: Pydantic v2 & pydantic-settings
- **Security**: JWT authentication, bcrypt password hashing, Role-Based Access Control (RBAC)
- **Testing**: pytest & httpx

---

## Architecture Overview

```
Windows Clients (Agents)
      │
      │ HTTPS (JSON REST)
      ▼
FastAPI Backend (/api/v1/)
      │
      ▼
PostgreSQL Database
      │
      ├── users (admin, operator, viewer)
      ├── clients (device identity, status, heartbeat)
      ├── backup_policies & paths (%USERPROFILE% universal expansions)
      ├── backup_jobs & backup_runs
      ├── backup_files (metadata & checksums)
      ├── recovery_points
      ├── restore_jobs (safeguarded workflow)
      ├── storage_repositories
      └── audit_logs (immutable operation tracking)
```

---

## Quickstart: Running with Docker (Recommended for PostgreSQL)

```bash
# Start PostgreSQL and FastAPI backend container
docker compose up -d

# View logs
docker compose logs -f backend
```

The API will be available at:
- Control Plane API: `http://localhost:8000/api/v1`
- Swagger UI Documentation: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

---

## Local Development (Without Docker)

### 1. Setup Virtual Environment

```bash
cd server
python -m venv .venv
.\.venv\Scripts\activate   # On Windows
# or: source .venv/bin/activate (Linux/Mac)
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Default development uses SQLite (`sqlite:///./backup.db`). To connect to a live PostgreSQL instance, set:
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/backupdb
```

### 3. Run Migrations & Seed Data

```bash
# Run database schema migrations
alembic -c alembic.ini upgrade head

# Seed initial admin user and 20 client workstations
python seed.py
```

### 4. Start Development Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Default Seed Credentials

| Role | Username | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `AdminPass123!` | Full administrative access, policy delete, client delete |
| **Operator** | `operator` | `Operator123!` | Backup trigger, client approve/disable, restore creation |
| **Viewer** | `viewer` | `Viewer123!` | Read-only telemetry access |

---

## Running Automated Tests

```bash
pytest server/tests -v
```

Tests verify:
- Database connectivity & health endpoint
- Authentication and JWT validation
- Unauthorized request protection
- Client registration, listing, and approval
- Agent heartbeat
- Backup policy CRUD
- Backup job creation & cancellation
- Dashboard summary aggregation
- Restore job creation with cross-client safeguard
- Role-Based Access Control (RBAC)

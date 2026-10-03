# Docker Deployment Guide (Sprint 20 Deployment Spike V1)

> **Important**: This provides a portable containerized deployment for local / self-hosted use. It is **NOT** a production cloud deployment.

## Overview & Architecture

SPECTRA can be deployed locally using Docker Compose with two containers and a persistent volume for the SQLite database:

```text
                  Host Browser
                       │
       ┌───────────────┴───────────────┐
       │ (Port 8080)                   │ (Port 8000)
       ▼                               ▼
┌───────────────┐               ┌───────────────┐
│   frontend    │ ──(API calls)─▶   backend     │
│ (Nginx static)│  (via browser)│  (FastAPI)    │
└───────────────┘               └───────┬───────┘
                                        │
                                        ▼
                             ┌─────────────────────┐
                             │ spectra-sqlite-data │
                             │  (Docker Volume)    │
                             │   /app/data/        │
                             └─────────────────────┘
```

1. **Backend (`spectra-backend`)**:
   - Python 3.13-slim running FastAPI via Uvicorn on port 8000.
   - Entrypoint script (`entrypoint.sh`) checks for the presence of `/app/data/spectra.db`. If a fresh/empty volume is mounted, it initializes the database from `/app/data-template/spectra.db` so the volume never masks the database.
   - Database operations write to the persistent volume `spectra-sqlite-data`.
   - Healthcheck monitors `GET /health` every 10 seconds.
2. **Frontend (`spectra-frontend`)**:
   - Nginx serving the compiled Vite production bundle on port 8080.
   - Configured with `VITE_API_BASE_URL` at build time (defaults to `http://localhost:8000`).
   - Starts only after the backend container passes its healthcheck (`condition: service_healthy`).

---

## 1. Prerequisites

- Docker Desktop, Docker Engine, or Podman (v20.10+)
- Docker Compose (v2.0+)

---

## 2. Environment Variables

Environment variables can be supplied in `.env` (gitignored) or passed via shell environment.

### Backend

| Variable | Default | Description |
|---|---|---|
| `SPECTRA_DATABASE_URL` | `sqlite:////app/data/spectra.db` | SQLAlchemy connection URL for SQLite in container |
| `SPECTRA_CORS_ORIGINS` | `http://localhost:8080,http://localhost:5173` | Comma-separated allowed CORS origins |
| `GEMINI_API_KEY` | *(empty)* | Optional Gemini API key for AI features |
| `GEMINI_MODEL` | *(empty)* | Optional Gemini model name |
| `BACKEND_PORT` | `8000` | Host port mapped to backend container |

### Frontend

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Browser-accessible URL of the backend API |
| `FRONTEND_PORT` | `8080` | Host port mapped to frontend container |

---

## 3. Build Command

Build both container images:

```bash
docker compose build
```

To build with a custom API base URL:

```bash
docker compose build --build-arg VITE_API_BASE_URL=http://your-server-ip:8000
```

---

## 4. Startup Command

Start the containers in detached mode:

```bash
docker compose up -d
```

Compose starts `backend` first, waits until `GET /health` returns 200, and then starts `frontend`.

---

## 5. Health Check

Verify backend health:

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

Or view Docker container health status:

```bash
docker compose ps
# STATUS column should show "(healthy)" for spectra-backend
```

---

## 6. Database Persistence

The SQLite database resides in the named volume `spectra-sqlite-data` mounted at `/app/data`.

### Empty Volume Masking Protection
When a volume is first created, `backend/entrypoint.sh` detects that `/app/data/spectra.db` does not exist yet and copies the pre-packaged baseline from `/app/data-template/spectra.db`. This guarantees that:
- An empty volume will never mask the existing dataset.
- The host repository's `data/spectra.db` is never modified or overwritten by container operations.

### Restart Survival
Data persists across normal container restarts and `docker compose down`:

```bash
# Stop and remove containers (named volume is preserved):
docker compose down

# Restart containers:
docker compose up -d
# All previous conversations and database changes are intact
```

---

## 7. Frontend / Backend Relationship

The frontend is a single-page application compiled into static HTML/JS/CSS served by Nginx. API requests originate from the **user's browser**, not from inside the Nginx container. Therefore:
- `VITE_API_BASE_URL` must point to the backend address reachable from the client browser (`http://localhost:8000` for local deployments).
- The backend's `SPECTRA_CORS_ORIGINS` includes `http://localhost:8080` so the browser can make cross-origin requests from the frontend port to the backend port.

---

## 8. Inspecting Logs

```bash
# View logs from all services:
docker compose logs -f

# View backend logs only:
docker compose logs -f backend

# View frontend logs only:
docker compose logs -f frontend
```

---

## 9. Stopping & Removing Containers

```bash
# Stop containers without removing:
docker compose stop

# Stop and remove containers (volume preserved):
docker compose down

# Stop and remove containers AND delete persistent database volume (destructive!):
docker compose down -v
```

---

## 10. Current Limitations

- **Not a Cloud Deployment**: Designed for local development and self-hosted single-node evaluation.
- **SQLite Single-Writer**: SQLite operates in single-process mode within the backend container.
- **No TLS**: Traffic is unencrypted HTTP. Place a reverse proxy (e.g. Caddy, Traefik, AWS ALB) in front for production HTTPS.
- **No Authentication**: API and frontend have no user authentication or RBAC.
- **No Horizontal Scaling**: Multiple backend replicas sharing SQLite is unsupported.

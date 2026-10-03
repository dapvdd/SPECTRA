# Production Readiness

## Architecture at Deployment Level

SPECTRA is a modular monolith client-server application:

```text
┌──────────────────────┐
│   React / Vite       │
│   Frontend (dist/)   │
└──────────┬───────────┘
           │ HTTP (configurable base URL)
           ▼
┌──────────────────────┐
│   FastAPI (Uvicorn)  │
│   Backend API        │
└──────────┬───────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
  SQLite      Gemini REST
  (local)      (AI only)
```

## Runtime Components

| Component | Technology | Configurable |
|-----------|------------|--------------|
| Frontend | React + Vite | `VITE_API_BASE_URL` |
| Backend | FastAPI + Uvicorn | Host/port via CLI |
| ORM | SQLAlchemy | `SPECTRA_DATABASE_URL` |
| Database | SQLite | `SPECTRA_DATABASE_URL` |
| AI | Gemini REST | `GEMINI_API_KEY`, `GEMINI_MODEL` |

## Environment Configuration

### Backend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SPECTRA_DATABASE_URL` | No | `sqlite:///./data/spectra.db` | SQLAlchemy database URL |
| `SPECTRA_CORS_ORIGINS` | No | `http://localhost:5173` | Comma-separated allowed origins |
| `GEMINI_API_KEY` | Yes (AI only) | — | Gemini API key |
| `GEMINI_MODEL` | Yes (AI only) | — | Gemini model name |

### Frontend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | No | `http://127.0.0.1:8000` | Backend API base URL |

## Startup Sequence

1. **Install backend dependencies**: `pip install -r requirements.txt`
2. **Initialize database** (additive only): `python -m backend.app.init_db`
3. **Start backend**: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
4. **Build frontend**: `npm run build`
5. **Serve frontend**: Deploy `dist/` to any static file server

## Health Verification

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

The health endpoint is deterministic and does not require Gemini credentials.

## Known Limitations

- **SQLite only**: No support for PostgreSQL/MySQL without code changes
- **Single process**: No horizontal scaling support
- **No authentication**: API is unauthenticated by design
- **No TLS**: HTTPS must be provided by a reverse proxy
- **Local file storage**: No cloud storage integration
- **Gemini dependency**: AI features require valid Gemini credentials

## What This Sprint Does NOT Provide

- Cloud deployment (AWS, GCP, Azure)
- Kubernetes orchestration
- Authentication/authorization
- CI/CD pipelines
- Database migrations (Alembic)
- Horizontal scaling
- TLS termination
- Log aggregation
- Monitoring/alerting

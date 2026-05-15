# ASCENT Backend

## Dev 1 Implementation

This backend is the infrastructure foundation for the ASCENT multi-agent pipeline.
It includes:
- FastAPI app skeleton and CORS configuration
- PostgreSQL async engine and SQLAlchemy models
- Webhook endpoints for `POST /webhooks/news` and `POST /webhooks/scheduled`
- Manual analysis endpoint at `POST /api/analyze`
- Report listing and detail endpoints at `GET /api/reports` and `GET /api/reports/{id}`
- Redis-backed activity WebSocket at `/ws/activity`
- Background pipeline dispatch stub with workflow persistence

## Quickstart

1. Copy environment config:

```powershell
copy .env.example .env
```

2. Start infrastructure:

```powershell
docker compose up -d
```

3. Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

4. Run the backend:

```powershell
uvicorn backend.main:app --reload
```

5. Verify health check:

```powershell
curl http://localhost:8000/health
```

## Notes

- The current pipeline dispatch is a stub that creates workflow state and publishes activity events.
- The database schema is created automatically at startup.
- The WebSocket endpoint uses Redis pub/sub to broadcast activity events.

# SignalForge Operations Runbook

## 1) Service inventory
- `signalforge-api` (FastAPI backend)
- `signalforge-frontend` (Next.js UI)

## 2) Health checks
- Liveness: `GET /api/health/live`
- Readiness: `GET /api/health/ready`
- Full status: `GET /api/health`

Readiness should return HTTP 200 before routing user traffic.

## 3) First-response flow (incident)
1. Check backend readiness endpoint.
2. Check logs for migration/database failures.
3. Validate ingestion scheduler is running (`scheduler_active=true` on `/api/health`).
4. Validate websocket connectivity from frontend alerts page.

## 4) Common failure modes
### Backend starts but readiness fails
- Cause: DB connectivity issue or scheduler not started.
- Action:
  - Confirm `DATABASE_URL`.
  - Confirm DB reachable from runtime.
  - Restart service after fixing env.

### Frontend loads but API requests fail (CORS/network)
- Cause: `CORS_ORIGINS` mismatch or wrong `NEXT_PUBLIC_API_URL`.
- Action:
  - Set backend `CORS_ORIGINS` to include frontend URL.
  - Set frontend `NEXT_PUBLIC_API_URL` to backend URL.
  - Redeploy both services.

### WebSocket alerts not connecting
- Cause: wrong ws origin URL.
- Action:
  - Set `NEXT_PUBLIC_WS_URL=wss://<backend-host>`.
  - Confirm websocket path `/ws/signals` is reachable.

## 5) Rollback strategy
- Keep last known good deployment in Render.
- On severe regressions, rollback both frontend and backend to previous release tags together.

## 6) Post-deploy validation script
1. Open frontend URL and confirm dashboard renders.
2. Hit backend `/api/health`, verify:
   - `status: healthy`
   - `database_ready: true`
   - `scheduler_active: true`
3. Trigger ingestion endpoint:
   - `POST /api/signals/ingest?count=10`
4. Confirm new signals appear in UI.
5. Confirm alerts page receives websocket updates.

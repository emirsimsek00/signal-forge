# Deployment Checklist

Use this checklist before shipping to staging/prod.

## Pre-flight
- [ ] All tests pass (`pytest` + frontend lint/build)
- [ ] DB migrations generated/reviewed/applied
- [ ] `.env` reviewed for required production variables
- [ ] External API keys validated (or mock mode explicitly intended)

## Release readiness
- [ ] Changelog/release notes updated
- [ ] Rollback plan defined
- [ ] Health endpoints verified (`/api/health`, `/api/health/live`, `/api/health/ready`)
- [ ] Incident notification channel configured
- [ ] Frontend ↔ backend URL wiring validated (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`, `CORS_ORIGINS`)

## Security
- [ ] CORS restricted to trusted origins
- [ ] Auth configured (no public admin endpoints)
- [ ] Secrets sourced from runtime secret store
- [ ] Dependency scan reviewed

## Runtime validation
- [ ] Ingestion scheduler running
- [ ] WebSocket alerts functioning
- [ ] Forecast/anomaly jobs produce expected records
- [ ] Dashboard, incidents, chat, and correlation routes all load

## Post-deploy
- [ ] Smoke test complete
- [ ] Error logs reviewed (no startup/migration failures)
- [ ] Performance baseline captured (latency, error rate)
- [ ] Backups verified (or snapshot strategy confirmed)

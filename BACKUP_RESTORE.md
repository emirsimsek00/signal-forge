# Backup and Restore Playbook

## Scope
Covers data protection for SignalForge's primary relational database.

## Recommended strategy (production)
- Use **PostgreSQL managed backups** (daily snapshot + PITR if available).
- Keep at least 7 daily backups and 4 weekly backups.
- Encrypt backups at rest and in transit.
- Perform restore drills at least monthly.

## PostgreSQL backup example
```bash
# Backup
pg_dump "$DATABASE_URL" --format=custom --file signalforge_$(date +%F_%H%M).dump

# Restore (to a clean DB)
pg_restore --clean --if-exists --no-owner --dbname "$DATABASE_URL" signalforge_2026-02-28_2300.dump
```

## SQLite fallback (dev/demo only)
```bash
# Backup
cp signalforge.db signalforge_$(date +%F_%H%M).db

# Restore
cp signalforge_2026-02-28_2300.db signalforge.db
```

## Restore validation checklist
1. API readiness passes: `/api/health/ready`
2. Signal count is within expected range
3. Incident list and notes are readable
4. Ingestion and websocket flows still operate
5. One synthetic end-to-end test alert can be created and resolved

## RPO / RTO targets (initial)
- RPO: 24h
- RTO: 60m

Adjust based on customer SLA commitments.

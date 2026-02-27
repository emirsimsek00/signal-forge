# SLO / SLI Targets (SignalForge)

These targets help present SignalForge as an operations-grade product.

## Service Level Indicators (SLIs)

1. **API availability**
   - Ratio of successful HTTP responses (`2xx`, `3xx`) over total requests.
2. **API latency (p95)**
   - 95th percentile response time for key routes:
     - `/api/signals`
     - `/api/dashboard/overview`
     - `/api/chat`
3. **Ingestion freshness**
   - Age of newest ingested signal vs current time.
4. **Incident workflow latency**
   - Time from anomaly detection to incident creation.
5. **WebSocket delivery health**
   - Successful alert messages delivered / attempted.

## Initial SLOs

- **Availability**: 99.5% monthly for core read APIs.
- **Latency**:
  - p95 < 500ms for read APIs
  - p95 < 1500ms for AI/chat endpoints in keyword mode
- **Ingestion freshness**: newest signal timestamp < 10 min old during active ingestion.
- **Incident creation**: anomaly-to-incident < 2 min for critical anomalies.

## Error budget

For 99.5% monthly availability, error budget is ~3h 39m per 30-day month.

## Alerting suggestions

- Page on sustained availability burn rate > 2x budget.
- Warn on p95 latency breach > 15 min.
- Warn when ingestion freshness exceeds threshold for >2 cycles.
- Page if anomaly detector fails consecutively for >3 runs.

## Resume/interview framing

"Defined SLI/SLOs and release gates for availability, latency, and ingestion freshness, aligning platform reliability with SRE-style error-budget management."

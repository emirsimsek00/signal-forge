# Security Policy

## Supported Versions
This project is currently maintained on `main`.

## Reporting a Vulnerability
If you find a security issue:
1. Do **not** open a public issue with exploit details.
2. Email the maintainer with:
   - impact
   - reproduction steps
   - affected endpoints/components
3. Expect acknowledgment within 72 hours.

## Security Baseline
- Secrets are environment-based (no hardcoded credentials)
- Tenant scoping is enforced in API/business logic paths
- Database migrations are version-controlled (Alembic)
- CI runs tests and migration smoke checks

## Recommended Hardening for deployment
- Enforce HTTPS only
- Restrict CORS to explicit frontend origins
- Configure rate limits at API gateway/reverse proxy
- Rotate API keys and JWT signing secrets periodically
- Enable dependency and secret scanning in CI
- Use least-privilege credentials for external integrations

## Out of scope
- Self-hosting misconfiguration outside this repository
- Third-party service outages beyond SignalForge control

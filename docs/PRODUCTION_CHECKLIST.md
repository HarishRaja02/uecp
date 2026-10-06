# Production Security Checklist

## Enforced by the application

- [x] Production rejects SQLite, in-memory rate limiting, insecure cookies and wildcard CORS
- [x] Production refresh cookies are HttpOnly, Secure and SameSite=Strict
- [x] Sensitive JSON responses use no-store caching
- [x] Credential secrets are returned only during provisioning and omitted from listings
- [x] Credential lifecycle actions require audit records and reasons where destructive
- [x] Alembic migrations are required outside test mode
- [x] Expiry processing, notification deduplication and delivery failure tracking
- [x] Admin notification log and manual expiry trigger

## Deployment verification

- [ ] PostgreSQL with least-privilege DB roles
- [ ] TLS everywhere + HSTS
- [ ] OIDC/enterprise SSO enabled
- [ ] WebAuthn/passkeys or strong MFA for administrators
- [ ] KMS/HSM-backed envelope encryption for secrets
- [ ] Redis-backed distributed rate limits (`RATE_LIMIT_STORAGE=redis://...`)
- [ ] Refresh-token rotation in HttpOnly Secure SameSite cookies
- [ ] ABAC/policy engine enabled for sensitive resources
- [ ] Append-only/tamper-evident audit storage
- [ ] WAF / API gateway / DDoS controls
- [ ] Dependency, secret and static scans in CI
- [ ] Backup + restore test + documented RPO/RTO
- [ ] Security test suite for IDOR/BOLA/tenant escape/privilege escalation
- [ ] Production seed/demo credentials removed
- [ ] Swagger disabled in production
- [ ] External security review / penetration test

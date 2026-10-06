# UECP Architecture

```text
React Admin Console
        |
      HTTPS
        |
 Flask API /api/v1
        |
  +-----+----------------------+
  |     |          |           |
 IAM  AuthZ    Subscription  Audit
  |     |          |           |
  +-----+----------+-----------+
              PostgreSQL
                 |
          Redis / workers
                 |
          External clients
       (Nanvi, future SaaS apps)
```

The core is application-agnostic. Applications register capabilities, permissions and environments; their business data remains outside UECP.

## Authorization decision
`Subject + Action + Resource + Context + Policy -> ALLOW/DENY`.

The current MVP implements the identity/tenant/platform-admin foundation. ABAC/policy evaluation, OIDC, WebAuthn, KMS secret storage and signed webhooks are defined as production expansion modules rather than unsafe mock implementations.

# UECP Threat Model

## Assets
- identities and credentials
- tenant membership and authorization state
- application registration credentials
- subscription state
- audit/security events
- administrative capabilities

## Primary attackers
Unauthenticated attacker, compromised user, malicious tenant administrator, compromised application, stolen API/refresh credential, insider, automated bot, database attacker, supply-chain attacker.

## Key threats and controls
| Threat | Impact | Core mitigation |
|---|---|---|
| Tenant escape / BOLA | Critical | Authoritative tenant derived server-side; membership validation; DB scoping |
| Privilege escalation | Critical | Central authorization dependency; role checks; deny-by-default |
| Token theft/replay | Critical | Short access lifetime; session records; planned refresh rotation; TLS |
| Credential leakage | Critical | Never store plaintext; production KMS; redaction; no secrets in repo |
| Brute force | High | Layered rate limits; suspicious-login events; MFA/OIDC production integration |
| Admin abuse | Critical | Separate platform admin; audit trail; re-auth/approval extensions |
| Subscription bypass | High | Backend subscription state, not frontend flags |
| Injection | High | ORM/parameterized queries; validation |
| Audit tampering | High | Append-oriented audit model; production append-only storage |

## Security invariants
1. Frontend state is never an authorization boundary.
2. Client-provided user, tenant, role, permission, or subscription values are never authoritative.
3. Security failures fail closed.
4. Production secrets are externalized.
5. Sensitive operations produce audit events.

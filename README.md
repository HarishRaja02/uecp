# Universal Enterprise Control Plane (UECP)

**Standalone • API-first • multi-tenant • security-first • no Docker**

UECP is a reusable control plane for multiple enterprise applications. Nanvi is only the first client application; no Nanvi business logic is embedded in the core.

## Stack
- **Frontend:** React.js + Vite + JavaScript
- **Backend:** Python + Flask
- **Database:** SQLite for local development; PostgreSQL for production
- **Cache/rate limits:** Redis in production; in-memory limiter locally
- **Auth:** RS256 short-lived access token + rotating HttpOnly refresh cookie
- **Passwords:** Argon2id

## Included capabilities
- Central identity and session management
- Platform-admin authentication boundary
- Organization/tenant isolation foundation
- Application registry with one-time application secret
- Application permission registry
- Server-side authorization endpoint for client applications
- Subscription states and automatic effective-access denial
- User suspend/freeze/disable with session revocation
- Audit events and security events
- Security Center and operational dashboard
- Feature-flag model
- Usage-record model
- Credential/webhook/security-policy model foundations
- PostgreSQL-ready schema
- API v1 structure
- Threat model and production checklist
- No Docker dependency

## Windows setup — no Docker

### 1. Python environment
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Environment and keys
```powershell
Copy-Item .env.example .env
.\scripts\generate_keys.ps1
```

If the API reports `Missing required security key` on login, run the key-generation
script again and restart the Flask process. Login is limited to five attempts per
minute; repeated retries can therefore return HTTP 429 until the limiter window
expires or the development process is restarted.

### 3. Seed local database
```powershell
python backend\seed.py
```

### 4. Start Flask API
```powershell
python run_backend.py
```

You can also use:
```powershell
python backend\app\main.py
```

Or from the backend directory:
```powershell
cd backend
python -m app.main
```

Health check: `http://localhost:8001/api/v1/health`
API landing page: `http://localhost:8001/` (links to the admin UI and health check).

### 5. Start React.js frontend
Open another PowerShell window:
```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5174/`.

### Seed credentials
Set a strong password only in the environment that runs the seed command:
```powershell
$env:SEED_ADMIN_PASSWORD = "use-a-unique-password-of-at-least-12-characters"
python backend\seed.py
Remove-Item Env:\SEED_ADMIN_PASSWORD
```
The seed command does not contain or print the administrator password.

## Client application integration
A client application such as Nanvi uses:
```text
Authorization: Bearer <UECP access token>
X-UECP-Application-Key: <application key>
```

Then it calls:
```text
POST /api/v1/authorize
```

UECP evaluates the user, tenant, organization state, subscription and registered permission on the backend. The application secret is stored as a hash and is shown only once when the application is registered.

### Credential validation
Client applications can validate a credential without exposing its secret to
the browser:
```text
POST /api/v1/credentials/validate
X-UECP-Application-Key: <application key>
{"credential": "<credential secret>"}
```
The response includes `allowed`, an effective status/reason, and the
credential's permission entitlements. A frozen or revoked ancestor denies all
descendants without copying state to child rows. The endpoint updates
`last_used_at` only after a credential secret is successfully verified.

### Expiry worker
Run the expiry pass from a scheduler such as Windows Task Scheduler or cron:
```powershell
$env:PYTHONPATH = "backend"
python backend\worker.py
```
The pass creates deduplicated pending notification records, moves credentials
into grace/frozen states, and freezes expired access grants. Configure the SMTP
settings in `.env` before adding an email delivery job.

### Admin credential provisioning
Platform administrators can open **Credentials** in the React dashboard and
choose **Provision access**. Select an organization, active application, plan,
expiry date and optional grace period. UECP creates one application access grant
and three root credentials. Each root secret is displayed once; copy it to the
customer through a secure channel before closing the dialog. Secrets cannot be
recovered from the dashboard.

The **Notifications** dashboard shows reminder, grace and expiry events,
delivery attempts and SMTP failures. Platform administrators can run an expiry
check manually for operations or leave the hourly `backend\worker.py` task as
the normal scheduler. Credential rows also support freeze, unfreeze, extend
and permanent revoke actions; destructive actions require a reason and are
written to the audit log.

## Production requirements
- PostgreSQL; SQLite is development-only.
- Redis-backed distributed rate limiting.
- Set `ENVIRONMENT=production`, `SECURE_COOKIES=true`, an explicit
  `CORS_ORIGINS` allowlist, and `RATE_LIMIT_STORAGE=redis://...`; the
  application refuses to start with SQLite, memory rate limiting, insecure
  cookies, or wildcard CORS in production.
- KMS/HSM/secret manager for signing keys and application secrets.
- TLS + reverse proxy/WAF.
- OIDC/enterprise SSO + MFA/WebAuthn.
- Alembic migrations in CI/CD.
- Exact CORS allowlist.
- Centralized observability with sensitive-data redaction.
- Encrypted, tested backups.
- Secret scanning, SAST, dependency audit and security tests.
- Independent penetration/security review.

UECP does **not** claim to be unbreakable or 100% secure. It is designed around deny-by-default, least privilege, defense in depth, tenant isolation, secure sessions and auditable privileged operations.

### Connecting a Vercel/AWS deployment

Hosting does not provide a universal remote-password control channel. Open the
**Integrations** page in the UECP admin panel to register the deployment. The
deployed application must implement a webhook receiver, for example:
`https://your-app.example.com/api/uecp/webhook`. Register that HTTPS URL for
the application in the admin panel and store the signing secret shown once.

The receiver must read the raw request body and verify
`X-UECP-Signature` as `HMAC-SHA256(secret, timestamp + "." + raw_body)`,
using `X-UECP-Timestamp`, rejecting old timestamps and invalid signatures.
After applying the command locally, it must return a 2xx response.

UECP sends commands through
`POST /api/v1/admin/webhooks/<webhook_id>/commands`. Supported commands are
`PASSWORD_RESET_REQUIRED`, `ACCESS_FREEZE`, and `ACCESS_RENEWED`. The deployed
application—not Vercel or AWS—changes its own user database or sessions. This
is what makes centralized control work regardless of hosting provider.

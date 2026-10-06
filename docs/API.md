# UECP API v1

## Public
- `GET /api/v1/health`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

## Platform admin
- `GET /api/v1/admin/overview`
- `GET /api/v1/admin/applications`
- `POST /api/v1/admin/applications` — returns the application key once
- `POST /api/v1/admin/applications/{id}/permissions`
- `GET /api/v1/admin/organizations`
- `POST /api/v1/admin/organizations`
- `GET /api/v1/admin/users`
- `POST /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{id}/status`
- `GET /api/v1/admin/subscriptions`
- `GET /api/v1/admin/audit`
- `GET /api/v1/admin/security-events`
- `POST /api/v1/admin/sessions/{id}/revoke`

## Client application integration
Client applications send `Authorization: Bearer <UECP access token>` and `X-UECP-Application-Key: <application key>`.

`POST /api/v1/authorize` checks the authenticated user, organization, subscription and registered application permission server-side. The application key is hashed at rest and shown only at creation time.

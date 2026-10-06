from datetime import datetime, timedelta, timezone

from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError

from app.core.security import ph
from app.core.time import as_utc
from app.models import Application, Credential, Organization, AccessGrant


ALLOWED_STATES = {'ACTIVE', 'EXPIRING', 'GRACE'}
TERMINAL_STATES = {'REVOKED'}


def _now():
    return datetime.now(timezone.utc)


def _expiry_state(expires_at, grace_days=0, now=None):
    if not expires_at:
        return 'ACTIVE', None
    now = now or _now()
    expiry = as_utc(expires_at)
    if expiry >= now:
        if expiry - now <= timedelta(days=30):
            return 'EXPIRING', 'expires_soon'
        return 'ACTIVE', None
    grace_until = expiry + timedelta(days=max(grace_days or 0, 0))
    if now <= grace_until:
        return 'GRACE', 'within_grace_period'
    return 'FROZEN', 'expired'


def _credential_graph(credential):
    rows = Credential.query.filter_by(access_grant_id=credential.access_grant_id).all()
    by_id = {row.id: row for row in rows}
    ancestors = []
    current = credential
    seen = set()
    while current.parent_id:
        if current.id in seen:
            return None, 'credential_cycle'
        seen.add(current.id)
        current = by_id.get(current.parent_id)
        if not current:
            return None, 'missing_parent'
        ancestors.append(current)
    return list(reversed(ancestors)), None


def effective_status(credential, now=None):
    now = now or _now()
    application = Application.query.get(credential.application_id)
    if not application or application.status != 'ACTIVE':
        return {'allowed': False, 'status': 'FROZEN', 'reason': 'application_inactive', 'credential_id': credential.id}
    organization = Organization.query.get(credential.organization_id)
    if not organization or organization.status != 'ACTIVE':
        return {'allowed': False, 'status': 'FROZEN', 'reason': 'organization_inactive', 'credential_id': credential.id}
    from app.services.authorization import subscription_active
    if not subscription_active(credential.organization_id):
        return {'allowed': False, 'status': 'FROZEN', 'reason': 'subscription_expired_or_inactive', 'credential_id': credential.id}
    grant = AccessGrant.query.get(credential.access_grant_id)
    if not grant:
        return {'allowed': False, 'status': 'FROZEN', 'reason': 'access_grant_missing', 'credential_id': credential.id}
    if grant.status in {'FROZEN', 'REVOKED', 'SUSPENDED', 'CANCELLED'}:
        return {'allowed': False, 'status': grant.status, 'reason': 'access_grant_inactive', 'credential_id': credential.id}
    grant_state, grant_reason = _expiry_state(grant.expires_at, grant.grace_days, now)
    if grant_state == 'FROZEN':
        return {'allowed': False, 'status': grant_state, 'reason': grant_reason, 'credential_id': credential.id}
    ancestors, graph_error = _credential_graph(credential)
    if graph_error:
        return {'allowed': False, 'status': 'FROZEN', 'reason': graph_error, 'credential_id': credential.id}
    for ancestor in ancestors:
        if ancestor.status in TERMINAL_STATES or ancestor.status == 'FROZEN':
            return {'allowed': False, 'status': ancestor.status, 'reason': 'ancestor_inactive', 'blocked_by': ancestor.id, 'credential_id': credential.id}
        state, reason = _expiry_state(ancestor.expires_at, grant.grace_days, now)
        if state == 'FROZEN':
            return {'allowed': False, 'status': state, 'reason': reason, 'blocked_by': ancestor.id, 'credential_id': credential.id}
    if credential.status in TERMINAL_STATES or credential.status == 'FROZEN':
        return {'allowed': False, 'status': credential.status, 'reason': 'credential_inactive', 'credential_id': credential.id}
    credential_state, credential_reason = _expiry_state(credential.expires_at, grant.grace_days, now)
    if credential_state == 'FROZEN':
        return {'allowed': False, 'status': credential_state, 'reason': credential_reason, 'credential_id': credential.id}
    states = [grant_state] + [_expiry_state(item.expires_at, grant.grace_days, now)[0] for item in ancestors] + [credential_state]
    effective = 'GRACE' if 'GRACE' in states else ('EXPIRING' if 'EXPIRING' in states else 'ACTIVE')
    return {'allowed': True, 'status': effective, 'reason': credential_reason or grant_reason or 'active', 'credential_id': credential.id}


def verify_credential_secret(credential, secret):
    if not credential.secret_hash:
        return False
    try:
        return ph.verify(credential.secret_hash, secret)
    except (InvalidHashError, VerifyMismatchError, VerificationError):
        return False


def subtree(credential):
    rows = Credential.query.filter_by(access_grant_id=credential.access_grant_id).all()
    children = {}
    for row in rows:
        children.setdefault(row.parent_id, []).append(row)
    result = []
    stack = [credential]
    while stack:
        current = stack.pop()
        result.append(current)
        stack.extend(children.get(current.id, []))
    return result

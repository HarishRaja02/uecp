from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from flask import Blueprint, jsonify, request, g

from app.db import db
from app.models import AccessGrant, Application, Credential, Organization, Plan
from app.core.security import hash_password
from app.core.time import as_utc
from app.security import auth_required, platform_admin
from app.services.audit import audit
from app.services.credentials import effective_status, subtree, verify_credential_secret


credentials_bp = Blueprint('credentials', __name__)


def _credential_row(credential):
    result = effective_status(credential)
    return {
        'id': credential.id,
        'name': credential.name,
        'kind': credential.kind,
        'parent_id': credential.parent_id,
        'root_id': credential.root_id,
        'depth': credential.depth,
        'status': credential.status,
        'effective_status': result['status'],
        'effective_allowed': result['allowed'],
        'effective_reason': result['reason'],
        'expires_at': credential.expires_at,
        'last_used_at': credential.last_used_at,
        'permissions': credential.permissions or [],
    }


def application_from_key():
    from hashlib import sha256
    raw = request.headers.get('X-UECP-Application-Key') or request.headers.get('X-Application-Key', '')
    if not raw:
        data = request.get_json(silent=True) or {}
        raw = data.get('application_key', '')
    if not raw:
        return None
    return Application.query.filter_by(
        application_key_hash=sha256(raw.encode()).hexdigest(),
        status='ACTIVE',
    ).first()


@credentials_bp.get('/admin/access-grants')
@platform_admin
def list_access_grants():
    grants = AccessGrant.query.order_by(AccessGrant.created_at.desc()).all()
    organizations = {item.id: item.name for item in Organization.query.all()}
    applications = {item.id: item.name for item in Application.query.all()}
    return jsonify(items=[{
        'id': grant.id,
        'organization_id': grant.organization_id,
        'organization': organizations.get(grant.organization_id, grant.organization_id),
        'application_id': grant.application_id,
        'application': applications.get(grant.application_id, grant.application_id),
        'plan_id': grant.plan_id,
        'status': grant.status,
        'expires_at': grant.expires_at,
        'grace_days': grant.grace_days,
        'credentials': [_credential_row(credential) for credential in grant.credentials],
    } for grant in grants])


def _parse_datetime(value, field='expires_at'):
    if not value:
        return None, jsonify(error=f'{field}_required', message=f'{field} is required'), 400
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None, jsonify(error=f'invalid_{field}', message=f'{field} must be ISO-8601'), 400
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed, None, None


def _new_credential(application_id, organization_id, grant_id, name, kind, expires_at, permissions):
    secret = f'uecp_cred_{token_urlsafe(32)}'
    return Credential(
        application_id=application_id,
        organization_id=organization_id,
        access_grant_id=grant_id,
        name=name,
        kind=kind,
        expires_at=expires_at,
        secret_hash=hash_password(secret),
        legacy_secret_ciphertext='',
        secret_last4=secret[-4:],
        permissions=permissions,
    ), secret


@credentials_bp.post('/admin/access-grants')
@platform_admin
def provision_access_grant():
    data = request.get_json(silent=True) or {}
    organization_id = str(data.get('organization_id', '')).strip()
    application_id = str(data.get('application_id', '')).strip()
    plan_id = str(data.get('plan_id', '')).strip()
    organization = Organization.query.get(organization_id)
    application = Application.query.filter_by(id=application_id, status='ACTIVE').first()
    plan = Plan.query.get(plan_id)
    if not organization or not application or not plan:
        return jsonify(error='invalid_provisioning_target', message='Organization, active application, and plan are required'), 404
    if AccessGrant.query.filter_by(organization_id=organization.id, application_id=application.id).first():
        return jsonify(error='access_grant_exists', message='This organization already has access to the application'), 409
    expires_at, error, status = _parse_datetime(data.get('expires_at'))
    if error:
        return error, status
    permissions = data.get('permissions') or []
    if not isinstance(permissions, list) or any(not isinstance(item, str) for item in permissions):
        return jsonify(error='invalid_permissions', message='permissions must be a list of strings'), 400
    grant = AccessGrant(organization_id=organization.id, application_id=application.id, plan_id=plan.id, expires_at=expires_at, grace_days=max(int(data.get('grace_days', 0)), 0))
    db.session.add(grant)
    db.session.flush()
    roots = []
    secrets = []
    cred_names = [
        f'{application.name} Primary Credential',
        f'{application.name} Secondary Backup Credential',
        f'{application.name} Worker Agent Credential'
    ]
    for cred_name in cred_names:
        root, secret = _new_credential(application.id, organization.id, grant.id, cred_name, 'ROOT', expires_at, permissions)
        db.session.add(root)
        db.session.flush()
        root.root_id = root.id
        root.path = f'/{root.id}/'
        roots.append(root)
        secrets.append(secret)
    audit(actor_id=g.principal['user'].id, organization_id=organization.id, application_id=application.id, action='ACCESS_GRANT_PROVISIONED', resource='access_grant', resource_id=grant.id, metadata={'root_count': 3})
    db.session.commit()
    return jsonify(access_grant_id=grant.id, roots=[{'id': root.id, 'name': root.name, 'secret': secret} for root, secret in zip(roots, secrets)], warning='Store these credential secrets securely. They cannot be recovered.'), 201


@credentials_bp.post('/credentials/children')
def create_child_credential():
    application = application_from_key()
    if not application:
        return jsonify(error='invalid_application_credential', message='A valid application key is required'), 401
    data = request.get_json(silent=True) or {}
    parent_secret = str(data.get('parent_credential', data.get('credential', '')))
    if not parent_secret:
        return jsonify(error='parent_credential_required', message='parent_credential is required'), 400
    candidates = Credential.query.filter_by(application_id=application.id, secret_last4=parent_secret[-4:]).all()
    parent = next((item for item in candidates if verify_credential_secret(item, parent_secret)), None)
    if not parent:
        return jsonify(error='invalid_credential', message='Parent credential is invalid'), 401
    parent_status = effective_status(parent)
    if not parent_status['allowed']:
        return jsonify(error='parent_inactive', message=parent_status['reason']), 403
    grant = AccessGrant.query.get(parent.access_grant_id)
    plan = Plan.query.get(grant.plan_id) if grant else None
    if not grant or not plan:
        return jsonify(error='access_grant_missing', message='Access grant is unavailable'), 403
    if parent.depth + 1 > plan.max_depth:
        return jsonify(error='max_depth_exceeded', message='The credential depth limit has been reached'), 409
    root_id = parent.root_id or parent.id
    direct_children = Credential.query.filter_by(parent_id=parent.id).count()
    if direct_children >= plan.max_children:
        return jsonify(error='max_children_exceeded', message='The child limit has been reached'), 409
    expires_at, error, status = _parse_datetime(data.get('expires_at'))
    if error:
        return error, status
    if parent.expires_at and expires_at > as_utc(parent.expires_at):
        return jsonify(error='expiry_exceeds_parent', message='A child cannot outlive its parent'), 400
    if grant.expires_at and expires_at > as_utc(grant.expires_at):
        return jsonify(error='expiry_exceeds_grant', message='A child cannot outlive its access grant'), 400
    permissions = data.get('permissions', parent.permissions or [])
    if not isinstance(permissions, list) or not set(permissions).issubset(set(parent.permissions or [])):
        return jsonify(error='permissions_exceed_parent', message='A child cannot have permissions its parent does not have'), 400
    child, secret = _new_credential(application.id, parent.organization_id, grant.id, str(data.get('name', 'Child')).strip() or 'Child', 'CHILD', expires_at, permissions)
    child.parent_id = parent.id
    child.root_id = root_id
    child.depth = parent.depth + 1
    db.session.add(child)
    db.session.flush()
    child.path = f'{parent.path or "/"}/{child.id}/'
    audit(actor_id=None, organization_id=parent.organization_id, application_id=application.id, action='CREDENTIAL_CHILD_CREATED', resource='credential', resource_id=child.id, metadata={'parent_id': parent.id})
    db.session.commit()
    return jsonify(id=child.id, name=child.name, secret=secret, parent_id=parent.id, root_id=root_id, depth=child.depth, permissions=child.permissions, warning='Store this credential secret securely. It cannot be recovered.'), 201


@credentials_bp.post('/credentials/validate')
def validate_credential():
    application = application_from_key()
    if not application:
        return jsonify(allowed=False, reason='invalid_application_credential'), 401
    data = request.get_json(silent=True) or {}
    secret = str(data.get('credential_secret', data.get('credential', data.get('secret', '')))).strip()
    if not secret:
        return jsonify(allowed=False, reason='credential_required'), 400
    cred_id = data.get('credential_id') or request.headers.get('X-Credential-ID')
    if cred_id:
        credential = Credential.query.filter_by(id=cred_id, application_id=application.id).first()
        if not credential or not verify_credential_secret(credential, secret):
            return jsonify(allowed=False, reason='invalid_credential'), 401
    else:
        candidates = Credential.query.filter_by(application_id=application.id, secret_last4=secret[-4:]).all()
        credential = next((item for item in candidates if verify_credential_secret(item, secret)), None)
        if not credential:
            return jsonify(allowed=False, reason='invalid_credential'), 401
    result = effective_status(credential)
    result['application_id'] = application.id
    result['organization_id'] = credential.organization_id
    result['credential_id'] = credential.id
    credential.last_used_at = datetime.now(timezone.utc)
    audit(
        actor_id=credential.id,
        organization_id=credential.organization_id,
        application_id=application.id,
        action='CREDENTIAL_VALIDATED',
        resource='credential',
        resource_id=credential.id,
        result='SUCCESS' if result['allowed'] else 'DENIED',
        reason=result.get('reason'),
        metadata={'entitlements': result.get('entitlements', [])}
    )
    db.session.commit()
    return jsonify(result), 200 if result['allowed'] else 403


@credentials_bp.get('/admin/credentials/<credential_id>/impact')
@platform_admin
def credential_impact(credential_id):
    credential = Credential.query.get(credential_id)
    if not credential:
        return jsonify(error='not_found', message='Credential not found'), 404
    affected = subtree(credential)
    return jsonify(credential_id=credential.id, affected_credentials=len(affected), affected_ids=[item.id for item in affected])


@credentials_bp.post('/admin/credentials/<credential_id>/action')
@platform_admin
def credential_action(credential_id):
    credential = Credential.query.get(credential_id)
    if not credential:
        return jsonify(error='not_found', message='Credential not found'), 404
    data = request.get_json(silent=True) or {}
    action = str(data.get('action', '')).strip().lower()
    reason = str(data.get('reason', '')).strip()
    if action not in {'freeze', 'unfreeze', 'extend', 'revoke'}:
        return jsonify(error='invalid_action', message='Action must be freeze, unfreeze, extend, or revoke'), 400
    if action in {'freeze', 'revoke'} and not reason:
        return jsonify(error='reason_required', message='A reason is required for this action'), 400
    affected = subtree(credential)
    if action == 'freeze':
        credential.status = 'FROZEN'
        credential.frozen_at = datetime.now(timezone.utc)
        credential.frozen_reason = reason
    elif action == 'unfreeze':
        if credential.status == 'REVOKED':
            return jsonify(error='credential_revoked', message='Revoked credentials cannot be unfrozen'), 409
        credential.status = 'ACTIVE'
        credential.frozen_at = None
        credential.frozen_reason = None
    elif action == 'revoke':
        credential.status = 'REVOKED'
        credential.frozen_reason = reason
    else:
        raw_expiry = data.get('expires_at')
        if not raw_expiry:
            return jsonify(error='expires_at_required', message='expires_at is required for extension'), 400
        try:
            new_expiry = datetime.fromisoformat(str(raw_expiry).replace('Z', '+00:00'))
        except ValueError:
            return jsonify(error='invalid_expires_at', message='expires_at must be ISO-8601'), 400
        if new_expiry.tzinfo is None:
            new_expiry = new_expiry.replace(tzinfo=timezone.utc)
        if credential.parent_id and credential.parent and credential.parent.expires_at and new_expiry > credential.parent.expires_at:
            return jsonify(error='expiry_exceeds_parent', message='A credential cannot outlive its parent'), 400
        credential.expires_at = new_expiry
        if credential.status == 'FROZEN' and credential.frozen_reason == 'expired':
            credential.status = 'ACTIVE'
            credential.frozen_reason = None
    audit(actor_id=g.principal['user'].id, organization_id=credential.organization_id, application_id=credential.application_id, action=f'CREDENTIAL_{action.upper()}', resource='credential', resource_id=credential.id, reason=reason or action, metadata={'affected_credentials': len(affected)})
    db.session.commit()
    return jsonify(id=credential.id, action=action, affected_credentials=len(affected), status=credential.status, expires_at=credential.expires_at)

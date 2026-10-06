from flask import Blueprint, jsonify, request, g
from hashlib import sha256
from app.db import db
from app.models import Application, Permission, Role, RolePermission, FeatureFlag
from app.security import auth_required
from app.services.authorization import organization_active, subscription_active, get_membership
from app.services.audit import audit
integration_bp=Blueprint('integration',__name__)
def app_from_key():
    raw=request.headers.get('X-UECP-Application-Key','')
    return Application.query.filter_by(application_key_hash=sha256(raw.encode()).hexdigest(),status='ACTIVE').first() if raw else None
def has_permission(user,org_id,app_id,code):
    if user.is_platform_admin:return True
    m=get_membership(user.id,org_id)
    if not m:return False
    if m.role in {'SUPER_ADMIN','ORGANIZATION_ADMIN'}:return True
    role=Role.query.filter_by(organization_id=org_id,name=m.role).first();perm=Permission.query.filter_by(application_id=app_id,code=code).first()
    return bool(role and perm and RolePermission.query.filter_by(role_id=role.id,permission_id=perm.id).first())
@integration_bp.post('/authorize')
@auth_required
def authorize():
    app=app_from_key()
    if not app:return jsonify(allowed=False,reason='invalid_application_credential'),401
    user=g.principal['user'];org_id=g.principal['claims'].get('tenant_id');data=request.get_json(silent=True) or {};action=str(data.get('action','')).strip();resource=str(data.get('resource','')).strip();permission=str(data.get('permission','')).strip()
    if not action or not resource or not permission:return jsonify(allowed=False,reason='invalid_authorization_request'),400
    if not organization_active(org_id):
        audit(actor_id=user.id,organization_id=org_id,application_id=app.id,action='AUTHORIZATION_DENIED',resource=resource,result='DENIED',reason='organization_inactive');db.session.commit();return jsonify(allowed=False,reason='organization_inactive'),403
    if not subscription_active(org_id):
        audit(actor_id=user.id,organization_id=org_id,application_id=app.id,action='AUTHORIZATION_DENIED',resource=resource,result='DENIED',reason='subscription_inactive');db.session.commit();return jsonify(allowed=False,reason='subscription_inactive'),403
    if not has_permission(user,org_id,app.id,permission):
        audit(actor_id=user.id,organization_id=org_id,application_id=app.id,action='AUTHORIZATION_DENIED',resource=resource,result='DENIED',reason='permission_denied');db.session.commit();return jsonify(allowed=False,reason='permission_denied'),403
    audit(actor_id=user.id,organization_id=org_id,application_id=app.id,action='AUTHORIZATION_ALLOWED',resource=resource,result='SUCCESS',metadata={'permission':permission,'action':action});db.session.commit();return jsonify(allowed=True,reason='authorized',application_id=app.id,organization_id=org_id)
@integration_bp.get('/features/<app_id>')
@auth_required
def features(app_id):
    app=app_from_key()
    if not app or app.id != app_id:return jsonify(error='invalid_application_credential',message='A valid application key is required'),401
    org_id=g.principal['claims'].get('tenant_id');rows=FeatureFlag.query.filter(FeatureFlag.application_id==app_id,((FeatureFlag.organization_id==org_id)|(FeatureFlag.organization_id.is_(None)))).all();return jsonify(features={x.key:x.enabled for x in rows if x.environment in (None,'production','development')})

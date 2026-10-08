from secrets import token_urlsafe
from hashlib import sha256
from flask import Blueprint, jsonify, request, g
from sqlalchemy import func, text
from app import limiter
from app.db import db
from app.models import *
from app.services.expiry import process_expirations
from app.services.webhooks import protect_secret, deliver
from app.core.config import settings
from app.security import platform_admin, invalidate_auth_cache
from app.core.security import hash_password
from app.services.audit import audit, security_event
from app.services.authorization import subscription_active

admin_bp=Blueprint('admin',__name__)

def row_user(u, membership=None):
    m = membership
    return {'id':u.id,'email':u.email,'status':u.status,'role':m.role if m else None,'organization_id':m.organization_id if m else None,'mfa_enabled':u.mfa_enabled,'is_platform_admin':u.is_platform_admin,'created_at':u.created_at}

@admin_bp.get('/overview')
@platform_admin
def overview():
    import time
    t0 = time.time()
    row = db.session.execute(text("""
        SELECT
            (SELECT count(*) FROM users) as users,
            (SELECT count(*) FROM users WHERE status = 'ACTIVE') as active_users,
            (SELECT count(*) FROM users WHERE status IN ('SUSPENDED', 'FROZEN', 'LOCKED')) as suspended_users,
            (SELECT count(*) FROM organizations) as organizations,
            (SELECT count(*) FROM applications WHERE status = 'ACTIVE') as active_applications,
            (SELECT count(*) FROM sessions WHERE revoked = false) as active_sessions,
            (SELECT count(*) FROM subscriptions WHERE status IN ('PAST_DUE', 'EXPIRED', 'SUSPENDED')) as subscription_issues,
            (SELECT count(*) FROM security_events WHERE resolved = false) as security_alerts,
            (SELECT count(*) FROM audit_events) as audit_events
    """)).mappings().first()
    t_query = time.time() - t0
    print(f">>> [OVERVIEW] Query took: {t_query:.3f}s")
    return jsonify(dict(row) if row else {})

@admin_bp.get('/organizations')
@platform_admin
def organizations():
    orgs = Organization.query.order_by(Organization.created_at.desc()).all()
    if not orgs:
        return jsonify(items=[])
    counts = dict(db.session.query(
        Membership.organization_id, func.count(Membership.id)
    ).group_by(Membership.organization_id).all())
    active_subs = set(r[0] for r in db.session.query(
        Subscription.organization_id
    ).filter(Subscription.status.in_(['ACTIVE', 'TRIAL'])).all())
    return jsonify(items=[{
        'id': o.id,
        'name': o.name,
        'status': o.status,
        'members': counts.get(o.id, 0),
        'subscription_active': o.id in active_subs,
        'created_at': o.created_at
    } for o in orgs])

@admin_bp.post('/organizations')
@platform_admin
def create_org():
    data=request.get_json(silent=True) or {}; name=str(data.get('name','')).strip()
    if not name or len(name)>200: return jsonify(error='invalid_name',message='Organization name is required'),400
    o=Organization(name=name); db.session.add(o); db.session.flush(); plan=Plan.query.filter_by(code='FREE').first()
    if plan: db.session.add(Subscription(organization_id=o.id,plan_id=plan.id,status='ACTIVE'))
    audit(actor_id=g.principal['user'].id,organization_id=o.id,action='ORGANIZATION_CREATED',resource='organization',resource_id=o.id); db.session.commit(); return jsonify(id=o.id,name=o.name,status=o.status),201

@admin_bp.get('/users')
@platform_admin
def users():
    user_list = User.query.order_by(User.created_at.desc()).all()
    if not user_list:
        return jsonify(items=[])
    memberships = Membership.query.all()
    m_by_user = {m.user_id: m for m in memberships}
    return jsonify(items=[row_user(u, m_by_user.get(u.id)) for u in user_list])

@admin_bp.post('/users')
@platform_admin
@limiter.limit('30 per minute')
def create_user():
    data=request.get_json(silent=True) or {}; email=str(data.get('email','')).strip().lower(); password=str(data.get('password','')); org_id=data.get('organization_id'); role=str(data.get('role','USER'))
    if User.query.filter_by(email=email).first(): return jsonify(error='email_exists',message='Email already exists'),409
    if not org_id or not Organization.query.get(org_id): return jsonify(error='organization_not_found',message='Organization not found'),404
    try: ph=hash_password(password)
    except Exception as e: return jsonify(error='invalid_password',message=str(e)),400
    u=User(email=email,password_hash=ph); db.session.add(u); db.session.flush(); m=Membership(user_id=u.id,organization_id=org_id,role=role); db.session.add(m); audit(actor_id=g.principal['user'].id,organization_id=org_id,action='USER_CREATED',resource='user',resource_id=u.id); db.session.commit(); return jsonify(row_user(u, m)),201

@admin_bp.patch('/users/<user_id>/status')
@platform_admin
def status(user_id):
    data=request.get_json(silent=True) or {}; new=str(data.get('status',''))
    if new not in {'ACTIVE','PENDING','SUSPENDED','FROZEN','DISABLED','LOCKED'}: return jsonify(error='invalid_status',message='Unsupported account status'),400
    u=User.query.get(user_id)
    if not u: return jsonify(error='not_found',message='User not found'),404
    if u.id==g.principal['user'].id and new!='ACTIVE': return jsonify(error='self_lockout',message='You cannot disable your current platform-admin session'),400
    u.status=new
    invalidate_auth_cache(user_id=u.id)
    if new in {'SUSPENDED','FROZEN','DISABLED','LOCKED'}: Session.query.filter_by(user_id=u.id,revoked=False).update({'revoked':True})
    audit(actor_id=g.principal['user'].id,action='USER_STATUS_CHANGED',resource='user',resource_id=u.id,reason=new); security_event('HIGH' if new!='ACTIVE' else 'INFO','USER_STATUS_CHANGED',u.id,details={'status':new}); db.session.commit(); m=Membership.query.filter_by(user_id=u.id).first(); return jsonify(row_user(u, m))

@admin_bp.get('/applications')
@platform_admin
def applications():
    apps = Application.query.order_by(Application.created_at.desc()).all()
    if not apps:
        return jsonify(items=[])
    perm_counts = dict(db.session.query(
        Permission.application_id, func.count(Permission.id)
    ).group_by(Permission.application_id).all())
    return jsonify(items=[{
        'id': a.id,
        'name': a.name,
        'application_key_last4': a.application_key_last4,
        'status': a.status,
        'capabilities': a.capabilities,
        'allowed_origins': a.allowed_origins,
        'owner_emails': a.owner_emails or [],
        'permissions': perm_counts.get(a.id, 0),
        'created_at': a.created_at
    } for a in apps])

@admin_bp.post('/applications')
@platform_admin
def create_application():
    data=request.get_json(silent=True) or {}; name=str(data.get('name','')).strip()
    if not name: return jsonify(error='invalid_name',message='Application name is required'),400
    from sqlalchemy import func
    existing = Application.query.filter(func.lower(Application.name) == func.lower(name)).first()
    if existing:
        return jsonify(error='duplicate_application_name', message=f"An application named '{name}' already exists. Duplicate application names are not permitted."), 409
    
    owner_emails = data.get('owner_emails') or []
    if isinstance(owner_emails, str):
        owner_emails = [e.strip().lower() for e in owner_emails.split(',') if e.strip()]
    client_email = str(data.get('client_email', '')).strip().lower()
    if client_email and client_email not in owner_emails:
        owner_emails.append(client_email)

    secret='uecp_'+token_urlsafe(32)
    a=Application(
        name=name,
        application_key_hash=sha256(secret.encode()).hexdigest(),
        application_key_last4=secret[-4:],
        capabilities=data.get('capabilities') or {},
        allowed_origins=data.get('allowed_origins') or [],
        owner_emails=owner_emails
    )
    db.session.add(a)
    db.session.flush()
    audit(actor_id=g.principal['user'].id,action='APPLICATION_REGISTERED',resource='application',resource_id=a.id)
    db.session.commit()
    return jsonify(id=a.id,name=a.name,owner_emails=a.owner_emails or [],application_key=secret,warning='Store this application key securely. It cannot be recovered after creation.'),201

@admin_bp.patch('/applications/<app_id>')
@platform_admin
def update_application(app_id):
    app = Application.query.get(app_id)
    if not app:
        return jsonify(error='not_found', message='Application not found'), 404
    data = request.get_json(silent=True) or {}
    if 'name' in data:
        new_name = str(data['name']).strip()
        if new_name:
            app.name = new_name
    if 'owner_emails' in data:
        raw = data['owner_emails']
        if isinstance(raw, str):
            emails = [e.strip().lower() for e in raw.split(',') if e.strip()]
        elif isinstance(raw, list):
            emails = [str(e).strip().lower() for e in raw if str(e).strip()]
        else:
            emails = []
        app.owner_emails = emails
    elif 'client_email' in data:
        ce = str(data['client_email']).strip().lower()
        app.owner_emails = [ce] if ce else []
    audit(actor_id=g.principal['user'].id, action='APPLICATION_UPDATED', resource='application', resource_id=app.id)
    db.session.commit()
    return jsonify(id=app.id, name=app.name, owner_emails=app.owner_emails or [], status=app.status)


@admin_bp.post('/applications/<app_id>/webhook')
@platform_admin
def register_webhook(app_id):
    application=Application.query.get(app_id)
    endpoint=str((request.get_json(silent=True) or {}).get('endpoint','')).strip()
    if not application: return jsonify(error='not_found',message='Application not found'),404
    if not endpoint.startswith('https://') and settings.environment == 'production': return jsonify(error='https_required',message='Webhook endpoints must use HTTPS in production'),400
    if not endpoint.startswith(('http://','https://')): return jsonify(error='invalid_endpoint',message='Endpoint must be an HTTP or HTTPS URL'),400
    if endpoint.count('://') > 1: return jsonify(error='invalid_endpoint',message='Endpoint contains duplicate protocols (e.g. https://http://). Please enter a valid URL.'),400
    secret=token_urlsafe(32)
    webhook=Webhook(application_id=application.id,endpoint=endpoint,secret_ciphertext=protect_secret(secret))
    db.session.add(webhook); db.session.flush()
    audit(actor_id=g.principal['user'].id,application_id=application.id,action='WEBHOOK_REGISTERED',resource='webhook',resource_id=webhook.id)
    db.session.commit()
    return jsonify(id=webhook.id,application_id=application.id,endpoint=endpoint,signing_secret=secret,events=['CREDENTIAL_FROZEN','CREDENTIAL_REVOKED','CREDENTIAL_EXTENDED','ACCESS_GRANT_FROZEN','PASSWORD_RESET_REQUIRED'],warning='Store the signing secret securely. It cannot be recovered.'),201

def _format_delivery_error(exc, endpoint):
    msg = str(exc)
    if 'getaddrinfo failed' in msg or 'Errno 11001' in msg:
        return f"Cannot resolve host for '{endpoint}'. Check for typos (such as 'https://http://' or invalid domains) or DNS issues."
    if 'Connection refused' in msg or 'Errno 10061' in msg:
        return f"Connection refused at '{endpoint}'. Make sure the webhook receiver server is running on that port."
    return msg

@admin_bp.get('/applications/<app_id>/webhooks')
@platform_admin
def list_webhooks(app_id):
    return jsonify(items=[{'id':x.id,'endpoint':x.endpoint,'active':x.active,'created_at':x.created_at} for x in Webhook.query.filter_by(application_id=app_id).all()])

@admin_bp.post('/webhooks/<webhook_id>/test')
@platform_admin
def test_webhook(webhook_id):
    webhook=Webhook.query.get(webhook_id)
    if not webhook or not webhook.active: return jsonify(error='not_found',message='Active webhook not found'),404
    try: deliver(webhook,'WEBHOOK_TEST',{'event_id':token_urlsafe(12),'message':'UECP webhook connection test'})
    except Exception as exc:
        return jsonify(error='delivery_failed',message=_format_delivery_error(exc, webhook.endpoint)),502
    return jsonify(ok=True)

@admin_bp.post('/webhooks/<webhook_id>/commands')
@platform_admin
def webhook_command(webhook_id):
    webhook=Webhook.query.get(webhook_id)
    data=request.get_json(silent=True) or {}
    command=str(data.get('command','')).strip().upper()
    if not webhook or not webhook.active: return jsonify(error='not_found',message='Active webhook not found'),404
    if command not in {'PASSWORD_RESET_REQUIRED','ACCESS_FREEZE','ACCESS_RENEWED'}: return jsonify(error='invalid_command',message='Unsupported deployment command'),400
    payload={'event_id':token_urlsafe(12),'target_user_id':data.get('target_user_id'),'credential_id':data.get('credential_id'),'reason':str(data.get('reason','')).strip()}
    if command == 'PASSWORD_RESET_REQUIRED' and not payload['target_user_id']:
        return jsonify(error='target_user_required',message='target_user_id is required for password reset'),400
    try: deliver(webhook,command,payload)
    except Exception as exc:
        return jsonify(error='delivery_failed',message=_format_delivery_error(exc, webhook.endpoint)),502
    audit(actor_id=g.principal['user'].id,application_id=webhook.application_id,action='WEBHOOK_COMMAND_SENT',resource='webhook',resource_id=webhook.id,metadata={'command':command})
    db.session.commit()
    return jsonify(ok=True,event=command)

@admin_bp.post('/applications/<app_id>/permissions')
@platform_admin
def add_permission(app_id):
    if not Application.query.get(app_id): return jsonify(error='not_found',message='Application not found'),404
    data=request.get_json(silent=True) or {}; code=str(data.get('code','')).strip()
    if not code or len(code)>200: return jsonify(error='invalid_permission',message='Permission code is required'),400
    if Permission.query.filter_by(application_id=app_id,code=code).first(): return jsonify(error='exists',message='Permission already exists'),409
    p=Permission(application_id=app_id,code=code,description=data.get('description')); db.session.add(p); db.session.flush(); audit(actor_id=g.principal['user'].id,action='PERMISSION_CREATED',resource='permission',resource_id=p.id,application_id=app_id); db.session.commit(); return jsonify(id=p.id,code=p.code),201

@admin_bp.get('/subscriptions')
@platform_admin
def subscriptions():
    rows=[]
    for s in Subscription.query.order_by(Subscription.starts_at.desc()).all():
        o=Organization.query.get(s.organization_id); p=Plan.query.get(s.plan_id)
        rows.append({'id':s.id,'organization':o.name if o else None,'organization_id':s.organization_id,'plan':p.code if p else None,'status':s.status,'expires_at':s.expires_at,'active':subscription_active(s.organization_id)})
    return jsonify(items=rows)

@admin_bp.get('/plans')
@platform_admin
def plans():
    return jsonify(items=[{'id':p.id,'code':p.code,'name':p.name,'max_children':p.max_children,'max_depth':p.max_depth,'default_term_days':p.default_term_days} for p in Plan.query.order_by(Plan.name.asc()).all()])

@admin_bp.get('/audit')
@platform_admin
def audit_log():
    limit=min(max(int(request.args.get('limit',50)),1),200); rows=AuditEvent.query.order_by(AuditEvent.timestamp.desc()).limit(limit).all()
    return jsonify(items=[{'id=x.id':x.id} for x in []] if False else [{'id':x.id,'timestamp':x.timestamp,'actor_id':x.actor_id,'organization_id':x.organization_id,'action':x.action,'resource':x.resource,'resource_id':x.resource_id,'result':x.result,'reason':x.reason,'ip':x.ip,'request_id':x.request_id} for x in rows])

@admin_bp.get('/notifications')
@platform_admin
def notifications():
    rows=NotificationLog.query.order_by(NotificationLog.created_at.desc()).limit(200).all()
    return jsonify(items=[{'id':x.id,'event_type':x.event_type,'recipient':x.recipient,'status':x.status,'attempts':x.attempts,'last_error':x.last_error,'sent_at':x.sent_at,'created_at':x.created_at,'credential_id':x.credential_id,'access_grant_id':x.access_grant_id} for x in rows])

@admin_bp.post('/expiry/process')
@platform_admin
def process_expiry():
    return jsonify(process_expirations()), 200

@admin_bp.get('/security-events')
@platform_admin
def security_events():
    rows=SecurityEvent.query.order_by(SecurityEvent.timestamp.desc()).limit(100).all()
    return jsonify(items=[{'id':x.id,'timestamp':x.timestamp,'severity':x.severity,'event_type':x.event_type,'organization_id':x.organization_id,'user_id':x.user_id,'ip':x.ip,'details':x.details,'resolved':x.resolved} for x in rows])

@admin_bp.post('/sessions/<session_id>/revoke')
@platform_admin
def revoke_session(session_id):
    s=Session.query.get(session_id)
    if not s: return jsonify(error='not_found',message='Session not found'),404
    s.revoked=True; invalidate_auth_cache(session_id=session_id); audit(actor_id=g.principal['user'].id,organization_id=s.organization_id,action='SESSION_REVOKED',resource='session',resource_id=s.id); db.session.commit(); return jsonify(ok=True)

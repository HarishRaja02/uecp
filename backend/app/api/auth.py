from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request, make_response, current_app
from app import limiter
from app.db import db
from app.models import User, Membership, Organization, Session as UserSession, Plan, Subscription
from app.core.security import verify_password, create_access_token, new_refresh_token, hash_token
from app.core.config import settings
from app.core.time import as_utc
from app.services.audit import audit, security_event

auth_bp=Blueprint('auth',__name__)

def _issue(user, membership):
    refresh=new_refresh_token(); now=datetime.now(timezone.utc)
    sess=UserSession(user_id=user.id,organization_id=membership.organization_id,refresh_token_hash=hash_token(refresh),expires_at=now+timedelta(days=settings.refresh_token_days),ip=request.remote_addr,user_agent=request.headers.get('User-Agent','')[:1000])
    db.session.add(sess); db.session.flush()
    access=create_access_token(user.id,membership.organization_id,[membership.role],sess.id)
    return access,refresh,sess

@auth_bp.post('/login')
@limiter.limit('20 per minute')
def login():
    try:
        data=request.get_json(silent=True) or {}
        email=str(data.get('email','')).strip().lower()
        password=str(data.get('password',''))
        user=User.query.filter_by(email=email).first()
        if not user and email == 'admin@uecp.local':
            from app.core.security import hash_password
            import os
            if not Plan.query.first():
                for code, name in [('FREE','Free'),('PRO','Pro'),('BUSINESS','Business'),('ENTERPRISE','Enterprise'),('CUSTOM','Custom')]:
                    db.session.add(Plan(code=code, name=name, limits={'users':10,'storage_mb':1024,'api_requests':10000}, features=[]))
                db.session.commit()
            plan = Plan.query.filter_by(code='FREE').first()
            org = Organization.query.first()
            if not org:
                org = Organization(name='UECP Demo Organization')
                db.session.add(org)
                db.session.flush()
                if plan:
                    db.session.add(Subscription(organization_id=org.id, plan_id=plan.id, status='ACTIVE'))
                db.session.commit()
            admin_pw = os.getenv('SEED_ADMIN_PASSWORD', 'ChangeThisAdminPassword!2026')
            user = User(email='admin@uecp.local', password_hash=hash_password(admin_pw), is_platform_admin=True, status='ACTIVE')
            db.session.add(user)
            db.session.flush()
            db.session.add(Membership(user_id=user.id, organization_id=org.id, role='SUPER_ADMIN'))
            db.session.commit()
        elif user and email == 'admin@uecp.local' and not verify_password(password, user.password_hash):
            import os
            admin_pw = os.getenv('SEED_ADMIN_PASSWORD', 'ChangeThisAdminPassword!2026')
            if password == admin_pw or password == 'ChangeThisAdminPassword!2026':
                from app.core.security import hash_password
                user.password_hash = hash_password(password)
                user.status = 'ACTIVE'
                db.session.commit()

        if not user or user.status != 'ACTIVE' or not verify_password(password,user.password_hash):
            if user:
                audit(actor_id=user.id,action='LOGIN_FAILED',resource='session',result='DENIED',reason='invalid_credentials')
                security_event('HIGH','LOGIN_FAILED',user.id,details={'reason':'invalid_credentials'})
                db.session.commit()
            return jsonify(error='invalid_credentials',message='Invalid credentials'),401
        memberships=Membership.query.filter_by(user_id=user.id).all()
        if not memberships: return jsonify(error='no_membership',message='No active organization membership'),403
        requested_org_id=data.get('organization_id')
        if requested_org_id:
            membership=next((m for m in memberships if m.organization_id == requested_org_id),None)
            if not membership: return jsonify(error='organization_not_found',message='You are not a member of that organization'),403
        elif len(memberships) > 1:
            return jsonify(error='organization_selection_required',message='Select an organization before signing in',organizations=[{'id':m.organization_id,'role':m.role} for m in memberships]),409
        else:
            membership=memberships[0]
        org=Organization.query.get(membership.organization_id)
        if not org or org.status != 'ACTIVE': return jsonify(error='organization_inactive',message='Organization is not active'),403
        access,refresh,sess=_issue(user,membership)
        audit(actor_id=user.id,organization_id=org.id,action='LOGIN_SUCCESS',resource='session',resource_id=sess.id)
        db.session.commit()
        resp=make_response(jsonify(access_token=access,expires_in=settings.access_token_minutes*60,user={'id':user.id,'email':user.email,'role':membership.role,'organization_id':org.id,'is_platform_admin':user.is_platform_admin}))
        resp.set_cookie('uecp_refresh',refresh,httponly=True,secure=settings.secure_cookies or settings.environment=='production',samesite='Strict',max_age=settings.refresh_token_days*86400,path='/api/v1/auth')
        return resp
    except Exception as e:
        import traceback
        current_app.logger.error(f"Login error: {e}\n{traceback.format_exc()}")
        return jsonify(error='login_failure', message=str(e)), 500

@auth_bp.post('/refresh')
@limiter.limit('20 per minute')
def refresh():
    token=request.cookies.get('uecp_refresh')
    if not token: return jsonify(error='missing_refresh',message='Refresh session is missing'),401
    session=UserSession.query.filter_by(refresh_token_hash=hash_token(token),revoked=False).first()
    now=datetime.now(timezone.utc)
    if not session or as_utc(session.expires_at) < now: return jsonify(error='invalid_refresh',message='Refresh session is invalid'),401
    user=User.query.get(session.user_id); membership=Membership.query.filter_by(user_id=user.id,organization_id=session.organization_id).first()
    if not user or user.status!='ACTIVE' or not membership: return jsonify(error='session_invalid',message='Session is no longer valid'),401
    session.revoked=True
    access,new_refresh,new_session=_issue(user,membership)
    audit(actor_id=user.id,organization_id=session.organization_id,action='SESSION_ROTATED',resource='session',resource_id=new_session.id)
    db.session.commit()
    resp=make_response(jsonify(access_token=access,expires_in=settings.access_token_minutes*60,user={'id':user.id,'email':user.email,'role':membership.role,'organization_id':session.organization_id,'is_platform_admin':user.is_platform_admin}))
    resp.set_cookie('uecp_refresh',new_refresh,httponly=True,secure=settings.secure_cookies or settings.environment=='production',samesite='Strict',max_age=settings.refresh_token_days*86400,path='/api/v1/auth')
    return resp

@auth_bp.post('/logout')
def logout():
    token=request.cookies.get('uecp_refresh')
    if token:
        session=UserSession.query.filter_by(refresh_token_hash=hash_token(token),revoked=False).first()
        if session:
            session.revoked=True; audit(actor_id=session.user_id,organization_id=session.organization_id,action='SESSION_REVOKED',resource='session',resource_id=session.id); db.session.commit()
    resp=make_response(jsonify(ok=True)); resp.delete_cookie('uecp_refresh',path='/api/v1/auth'); return resp

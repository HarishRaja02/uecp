import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.core.config import settings
from app.db import db

limiter = Limiter(key_func=get_remote_address, default_limits=["300 per minute"], storage_uri=settings.rate_limit_storage)
from app.api.auth import auth_bp
from app.api.admin import admin_bp
from app.api.health import health_bp
from app.api.integration import integration_bp
from app.api.credentials import credentials_bp

def create_app(test_config=None):
    app = Flask(__name__)
    db_url = settings.database_url
    engine_options = {}

    if os.getenv('VERCEL'):
        from sqlalchemy.pool import NullPool
        engine_options['poolclass'] = NullPool

    if 'postgres' in db_url:
        engine_options['connect_args'] = {'connect_timeout': 3}
        if os.getenv('VERCEL'):
            try:
                from sqlalchemy import create_engine, text
                test_engine = create_engine(db_url, poolclass=NullPool, connect_args={'connect_timeout': 3})
                with test_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                test_engine.dispose()
            except Exception as err:
                app.logger.warning(f"PostgreSQL connection failed ({err}). Falling back to SQLite at /tmp/uecp.db")
                db_url = "sqlite:////tmp/uecp.db"
                engine_options = {}

    app.config.update(
        SECRET_KEY=settings.flask_secret_key,
        SQLALCHEMY_DATABASE_URI=db_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        JSON_SORT_KEYS=False,
    )
    if engine_options:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    limiter.init_app(app)
    if settings.cors_origins:
        CORS(app, origins=settings.cors_origins.split(','), supports_credentials=True)

    @app.get('/')
    def index():
        return '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>UECP API</title>
  <style>
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f4f6fb; color: #172033; font: 16px/1.5 system-ui, sans-serif; }
    main { width: min(560px, calc(100% - 48px)); padding: 32px; border: 1px solid #e2e7f0; border-radius: 16px; background: white; box-shadow: 0 12px 36px #17203312; }
    h1 { margin: 0 0 8px; font-size: 1.6rem; }
    p { color: #526078; }
    a { color: #3157c8; }
    .status { color: #167447; font-weight: 600; }
    .links { display: flex; flex-wrap: wrap; gap: 18px; margin-top: 24px; }
  </style>
</head>
<body>
  <main>
    <h1>UECP API is running</h1>
    <p class="status">The backend server is available.</p>
    <p>The admin interface runs separately. Start it from the <code>frontend</code> folder with <code>npm run dev</code>.</p>
    <div class="links">
      <a href="http://localhost:5174/">Open the admin interface</a>
      <a href="/api/v1/health">Check API health</a>
    </div>
  </main>
</body>
</html>'''

    @app.get('/favicon.ico')
    def favicon():
        return '', 204

    app.register_blueprint(health_bp, url_prefix='/api/v1')
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/v1/admin')
    app.register_blueprint(integration_bp, url_prefix='/api/v1')
    app.register_blueprint(credentials_bp, url_prefix='/api/v1')

    @app.after_request
    def security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Cache-Control', 'no-store' if request_is_sensitive(response) else 'no-cache')
        if settings.environment == 'production':
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return response

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error='payload_too_large', message='Request payload is too large'), 413

    @app.errorhandler(429)
    def too_many(_):
        return jsonify(error='rate_limited', message='Too many requests'), 429

    @app.errorhandler(Exception)
    def handle_unhandled_exception(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify(error=e.name.lower().replace(' ', '_'), message=e.description), e.code
        app.logger.error(f"Internal Error: {e}", exc_info=True)
        return jsonify(error='internal_error', message=str(e)), 500

    with app.app_context():
        try:
            db.create_all()
            from app.models import User, Plan, Organization, Subscription, Membership
            from app.core.security import hash_password
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
            admin_user = User.query.filter_by(email='admin@uecp.local').first()
            admin_pw = os.getenv('SEED_ADMIN_PASSWORD', 'ChangeThisAdminPassword!2026')
            if not admin_user:
                admin_user = User(email='admin@uecp.local', password_hash=hash_password(admin_pw), is_platform_admin=True)
                db.session.add(admin_user)
                db.session.flush()
                db.session.add(Membership(user_id=admin_user.id, organization_id=org.id, role='SUPER_ADMIN'))
                db.session.commit()
            else:
                admin_user.status = 'ACTIVE'
                db.session.commit()

            # Seed standard default client application and credentials
            from app.models import Application, AccessGrant, Credential
            from hashlib import sha256
            from datetime import datetime, timezone, timedelta

            app_id = '515c0c0f-56ef-4db9-a11a-3ca265d272a7'
            raw_app_key = 'uecp_KJ2cFJ4N6shuAY1xq2-BrLHw56q49Rv9I75guGVOsf8'
            key_hash = sha256(raw_app_key.encode()).hexdigest()
            app_rec = db.session.get(Application, app_id) or Application.query.filter_by(name='Nanvi AI Enterprise Assistant').first()
            if not app_rec:
                app_rec = Application(
                    id=app_id,
                    name='Nanvi AI Enterprise Assistant',
                    application_key_hash=key_hash,
                    application_key_last4=raw_app_key[-4:],
                    capabilities={'chat': True, 'rag': True, 'audit': True},
                    allowed_origins=['*'],
                    owner_emails=['admin@uecp.local'],
                    status='ACTIVE',
                )
                db.session.add(app_rec)
                db.session.flush()
            else:
                app_rec.application_key_hash = key_hash
                app_rec.application_key_last4 = raw_app_key[-4:]
                app_rec.status = 'ACTIVE'
                db.session.flush()

            grant = AccessGrant.query.filter_by(organization_id=org.id, application_id=app_rec.id).first()
            if not grant:
                grant = AccessGrant(
                    organization_id=org.id,
                    application_id=app_rec.id,
                    plan_id=plan.id if plan else None,
                    status='ACTIVE',
                    expires_at=datetime.now(timezone.utc) + timedelta(days=3650),
                    grace_days=30,
                )
                db.session.add(grant)
                db.session.flush()

            standard_creds = [
                ('b53f18de-4546-4364-9b3c-5ff410dab2d8', 'Nanvi Primary Credential', 'uecp_cred_s-p3EIGFCUpbv8usqcFqQuqWgl2wrJKkKcv2ZUrDyZo'),
                ('525fd565-8d7c-4648-a4db-2db94cc6d5fa', 'Nanvi Secondary Backup Credential', 'uecp_cred_exys1oxszozn-odvZb_waUfV5S7d5ALYP5imumV9hTs'),
                ('d3d0dece-5080-4c0d-a081-204139059739', 'Nanvi Worker Agent Credential', 'uecp_cred_THCN54mOjCpXuFBUxHpvoYNs6XX348d6-i1-PTcR6rw'),
            ]
            for cid, cname, csecret in standard_creds:
                cred = db.session.get(Credential, cid)
                if not cred:
                    cred = Credential(
                        id=cid,
                        application_id=app_rec.id,
                        organization_id=org.id,
                        access_grant_id=grant.id,
                        name=cname,
                        kind='ROOT',
                        status='ACTIVE',
                        expires_at=datetime.now(timezone.utc) + timedelta(days=3650),
                        secret_hash=hash_password(csecret),
                        secret_last4=csecret[-4:],
                        permissions=['*', 'ai.chat', 'ai:chat', 'documents.read', 'documents.write', 'email.read', 'reports.download'],
                        root_id=cid,
                        path=f'/{cid}/',
                    )
                    db.session.add(cred)
                else:
                    cred.secret_hash = hash_password(csecret)
                    cred.secret_last4 = csecret[-4:]
                    cred.status = 'ACTIVE'
                    cred.expires_at = datetime.now(timezone.utc) + timedelta(days=3650)
                    cred.application_id = app_rec.id
                    cred.access_grant_id = grant.id
            db.session.commit()
        except Exception as err:
            app.logger.warning(f"Database auto-setup: {err}")

    return app

def request_is_sensitive(response):
    return response.headers.get('Content-Type','').startswith('application/json')

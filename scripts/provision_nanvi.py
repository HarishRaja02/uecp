import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent / 'backend'
sys.path.insert(0, str(backend_dir))

from app import create_app
from app.db import db
from app.models import Application, Organization, Plan, AccessGrant, Credential
from app.api.credentials import _new_credential
from secrets import token_urlsafe
from hashlib import sha256
from datetime import datetime, timezone, timedelta

app = create_app()
with app.app_context():
    app_record = Application.query.filter_by(name='Nanvi AI Enterprise Assistant').first()
    if not app_record:
        raw_app_key = 'uecp_' + token_urlsafe(32)
        app_record = Application(
            name='Nanvi AI Enterprise Assistant',
            application_key_hash=sha256(raw_app_key.encode()).hexdigest(),
            application_key_last4=raw_app_key[-4:],
            capabilities={'chat': True, 'rag': True, 'audit': True},
            allowed_origins=['http://localhost:5173', 'http://localhost:8000', 'http://127.0.0.1:8000'],
            owner_emails=['admin@uecp.local']
        )
        db.session.add(app_record)
        db.session.flush()
    else:
        raw_app_key = 'uecp_' + token_urlsafe(32)
        app_record.application_key_hash = sha256(raw_app_key.encode()).hexdigest()
        app_record.application_key_last4 = raw_app_key[-4:]
        db.session.flush()

    org = Organization.query.first()
    plan = Plan.query.filter_by(code='ENTERPRISE').first() or Plan.query.first()

    grant = AccessGrant.query.filter_by(organization_id=org.id, application_id=app_record.id).first()
    expires_at = datetime.now(timezone.utc) + timedelta(days=365)
    if not grant:
        grant = AccessGrant(
            organization_id=org.id,
            application_id=app_record.id,
            plan_id=plan.id,
            expires_at=expires_at,
            grace_days=14
        )
        db.session.add(grant)
        db.session.flush()

    root, raw_cred_secret = _new_credential(
        app_record.id, org.id, grant.id, 'Nanvi Primary Credential', 'ROOT', expires_at, ['ai:chat', 'ai:search', 'enterprise:access']
    )
    db.session.add(root)
    db.session.flush()
    root.root_id = root.id
    root.path = f'/{root.id}/'
    db.session.commit()

    print('=== UECP PROVISIONING SUMMARY ===')
    print(f'UECP_ENABLED=true')
    print(f'UECP_BASE_URL=http://localhost:8001/api/v1')
    print(f'UECP_APPLICATION_ID={app_record.id}')
    print(f'UECP_APPLICATION_KEY={raw_app_key}')
    print(f'UECP_CREDENTIAL_ID={root.id}')
    print(f'UECP_CREDENTIAL_SECRET={raw_cred_secret}')
    print(f'UECP_VALIDATION_TIMEOUT_SECONDS=5')
    print(f'UECP_CACHE_TTL_SECONDS=60')

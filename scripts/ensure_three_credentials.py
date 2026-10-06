import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent / 'backend'
sys.path.insert(0, str(backend_dir))

from app import create_app
from app.db import db
from app.models import Application, Organization, AccessGrant, Credential
from app.api.credentials import _new_credential
from datetime import datetime, timezone, timedelta

app = create_app()
with app.app_context():
    app_rec = Application.query.filter_by(name='Nanvi AI Enterprise Assistant').first()
    if not app_rec:
        print('Nanvi app not found')
        sys.exit(1)

    org = Organization.query.first()
    grant = AccessGrant.query.filter_by(organization_id=org.id, application_id=app_rec.id).first()
    expires_at = grant.expires_at or (datetime.now(timezone.utc) + timedelta(days=365))
    perms = ['*', 'ai.chat', 'ai:chat', 'documents.read', 'documents.write', 'email.read', 'reports.download']

    existing = Credential.query.filter_by(application_id=app_rec.id).all()
    print('Existing count:', len(existing))
    needed = 3 - len(existing)

    new_creds = []
    if needed > 0:
        names = ['Nanvi Secondary Backup Credential', 'Nanvi Worker Agent Credential']
        for i in range(needed):
            c_name = names[i] if i < len(names) else f'Nanvi Scoped Credential {i+2}'
            c, secret = _new_credential(app_rec.id, org.id, grant.id, c_name, 'ROOT', expires_at, perms)
            db.session.add(c)
            db.session.flush()
            c.root_id = c.id
            c.path = f'/{c.id}/'
            new_creds.append((c.id, c.name, secret))
        db.session.commit()

    all_creds = Credential.query.filter_by(application_id=app_rec.id).all()
    print('Total Nanvi credentials count now:', len(all_creds))
    for c in all_creds:
        print(f' - ID: {c.id} | Name: {c.name} | Kind: {c.kind} | Status: {c.status}')

    for cid, cname, sec in new_creds:
        print(f'NEW CREATED -> Name: {cname} | ID: {cid} | Secret: {sec}')

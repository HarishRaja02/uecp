import os, tempfile
from hashlib import sha256
import pytest
os.environ['ENVIRONMENT']='test'
os.environ['DATABASE_URL']='sqlite:///:memory:'
os.environ['AUTO_CREATE_TABLES']='true'

def test_password_hashing():
    from app.core.security import hash_password, verify_password
    h=hash_password('A-very-long-test-password-2026!')
    assert h != 'A-very-long-test-password-2026!'
    assert verify_password('A-very-long-test-password-2026!',h)
    assert not verify_password('wrong',h)

def test_app_health():
    from app import create_app
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:'})
    with app.test_client() as c:
        r=c.get('/api/v1/health'); assert r.status_code==200; assert r.json['status']=='ok'

@pytest.fixture
def seeded_app(tmp_path):
    from app import create_app
    from app.db import db
    from app.models import Organization, User, Membership, Subscription, Plan, Application, Permission
    from app.core.security import hash_password
    from app.core.config import settings
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    private_path=tmp_path/'jwt_private.pem'
    public_path=tmp_path/'jwt_public.pem'
    private_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    public_path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    object.__setattr__(settings,'jwt_private_key_path',str(private_path))
    object.__setattr__(settings,'jwt_public_key_path',str(public_path))

    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:','AUTO_CREATE_TABLES':True})
    with app.app_context():
        plan=Plan(code='TEST',name='Test',limits={},features=[])
        org=Organization(name='Test organization')
        user=User(email='multi@example.test',password_hash=hash_password('A-very-long-test-password-2026!'))
        db.session.add_all([plan,org,user]); db.session.flush()
        db.session.add(Subscription(organization_id=org.id,plan_id=plan.id,status='ACTIVE'))
        db.session.add(Membership(user_id=user.id,organization_id=org.id,role='USER'))
        app_secret='uecp_test_key'
        client_app=Application(name='Test client',application_key_hash=sha256(app_secret.encode()).hexdigest(),application_key_last4='_key')
        db.session.add(client_app); db.session.flush()
        db.session.add(Permission(application_id=client_app.id,code='read:test'))
        db.session.commit()
        app.test_data={'user_id':user.id,'organization_id':org.id,'application_id':client_app.id,'application_key':app_secret}
    return app

def test_authorize_denies_frozen_organization(seeded_app):
    from app.db import db
    from app.models import Organization

    with seeded_app.test_client() as client:
        login=client.post('/api/v1/auth/login',json={'email':'multi@example.test','password':'A-very-long-test-password-2026!'})
        token=login.json['access_token']
    with seeded_app.app_context():
        org=Organization.query.get(seeded_app.test_data['organization_id'])
        org.status='FROZEN'
        db.session.commit()
    with seeded_app.test_client() as client:
        response=client.post('/api/v1/authorize',headers={'Authorization':f'Bearer {token}','X-UECP-Application-Key':seeded_app.test_data['application_key']},json={'action':'read','resource':'test','permission':'read:test'})
        assert response.status_code==403
        assert response.json['reason']=='organization_inactive'

def test_features_requires_matching_application_key(seeded_app):
    with seeded_app.test_client() as client:
        login=client.post('/api/v1/auth/login',json={'email':'multi@example.test','password':'A-very-long-test-password-2026!'})
        token=login.json['access_token']
        response=client.get(f"/api/v1/features/{seeded_app.test_data['application_id']}",headers={'Authorization':f'Bearer {token}'})
        assert response.status_code==401

def test_access_grant_listing_never_exposes_credential_secrets(seeded_app):
    from app.db import db
    from app.models import User, Plan
    from datetime import datetime, timezone, timedelta

    with seeded_app.app_context():
        user=User.query.get(seeded_app.test_data['user_id'])
        user.is_platform_admin=True
        db.session.commit()
        plan_id=Plan.query.first().id
    with seeded_app.test_client() as client:
        login=client.post('/api/v1/auth/login',json={'email':'multi@example.test','password':'A-very-long-test-password-2026!'})
        token=login.json['access_token']
        response=client.post('/api/v1/admin/access-grants',headers={'Authorization':f'Bearer {token}'},json={
            'organization_id':seeded_app.test_data['organization_id'],
            'application_id':seeded_app.test_data['application_id'],
            'plan_id':plan_id,
            'expires_at':(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(),
        })
        assert response.status_code == 201
        roots=response.json['roots']
        listing=client.get('/api/v1/admin/access-grants',headers={'Authorization':f'Bearer {token}'})
        assert listing.status_code == 200
        payload=str(listing.json)
        assert roots[0]['secret'] not in payload
        assert 'secret_hash' not in payload

def test_login_requires_organization_when_membership_is_ambiguous(seeded_app):
    from app.db import db
    from app.models import Organization, Membership, User

    with seeded_app.app_context():
        second=Organization(name='Second organization')
        db.session.add(second); db.session.flush()
        db.session.add(Membership(user_id=seeded_app.test_data['user_id'],organization_id=second.id,role='USER'))
        db.session.commit()
    with seeded_app.test_client() as client:
        response=client.post('/api/v1/auth/login',json={'email':'multi@example.test','password':'A-very-long-test-password-2026!'})
        assert response.status_code==409
        assert response.json['error']=='organization_selection_required'

def test_phase_one_access_grant_and_credential_hierarchy_schema(seeded_app):
    from app.db import db
    from app.models import AccessGrant, Credential, NotificationRule, NotificationLog, Plan, Application

    with seeded_app.app_context():
        plan=Plan.query.filter_by(code='TEST').one()
        plan.max_children=3
        plan.max_depth=4
        plan.default_term_days=90
        application=Application.query.get(seeded_app.test_data['application_id'])
        application.owner_emails=['developer@example.test']
        grant=AccessGrant(organization_id=seeded_app.test_data['organization_id'],application_id=application.id,plan_id=plan.id,grace_days=7)
        db.session.add(grant)
        db.session.flush()
        from app.core.security import hash_password
        root_secret='root-secret-for-validation-2026'
        root=Credential(application_id=application.id,organization_id=seeded_app.test_data['organization_id'],access_grant_id=grant.id,name='Root 1',kind='ROOT',root_id=None,depth=0,secret_hash=hash_password(root_secret),secret_last4=root_secret[-4:],permissions=['read:test'])
        db.session.add(root)
        db.session.flush()
        root.root_id=root.id
        child=Credential(application_id=application.id,organization_id=seeded_app.test_data['organization_id'],access_grant_id=grant.id,parent_id=root.id,root_id=root.id,name='Child A',kind='CHILD',path=f'/{root.id}/',depth=1,secret_hash='argon2id-child',secret_last4='hild',permissions=['read:test'])
        db.session.add_all([child,NotificationRule(access_grant_id=grant.id,event_type='EXPIRY_REMINDER',days_before=30,recipients=['developer@example.test']),NotificationLog(notification_key=f'{grant.id}:EXPIRY_REMINDER:30:developer@example.test',access_grant_id=grant.id,event_type='EXPIRY_REMINDER',recipient='developer@example.test')])
        db.session.commit()
        assert grant.credentials == [root, child]
        assert child.parent is root
        assert child.root_id == root.id
        assert application.owner_emails == ['developer@example.test']
        assert plan.max_children == 3

def test_credential_validate_denies_when_root_is_frozen(seeded_app):
    from app.db import db
    from app.models import AccessGrant, Credential, Plan, Application
    from app.core.security import hash_password

    root_secret='root-secret-for-validation-2026'
    with seeded_app.app_context():
        plan=Plan.query.filter_by(code='TEST').one()
        application=Application.query.get(seeded_app.test_data['application_id'])
        grant=AccessGrant(organization_id=seeded_app.test_data['organization_id'],application_id=application.id,plan_id=plan.id)
        root=Credential(application_id=application.id,organization_id=seeded_app.test_data['organization_id'],access_grant=grant,name='Root',kind='ROOT',depth=0,secret_hash=hash_password(root_secret),secret_last4=root_secret[-4:],permissions=['read:test'])
        db.session.add(root)
        db.session.commit()
        root.status='FROZEN'
        db.session.commit()
    with seeded_app.test_client() as client:
        response=client.post('/api/v1/credentials/validate',headers={'X-UECP-Application-Key':seeded_app.test_data['application_key']},json={'credential':root_secret})
        assert response.status_code==403
        assert response.json['reason']=='credential_inactive'

def test_effective_status_denies_child_when_ancestor_is_frozen(seeded_app):
    from app.db import db
    from app.models import AccessGrant, Credential, Plan, Application
    from app.core.security import hash_password
    from app.services.credentials import effective_status

    with seeded_app.app_context():
        plan=Plan.query.filter_by(code='TEST').one()
        application=Application.query.get(seeded_app.test_data['application_id'])
        grant=AccessGrant(organization_id=seeded_app.test_data['organization_id'],application_id=application.id,plan_id=plan.id)
        root=Credential(application_id=application.id,organization_id=seeded_app.test_data['organization_id'],access_grant=grant,name='Root',kind='ROOT',depth=0,secret_hash=hash_password('another-root-secret-2026'),secret_last4='2026',permissions=['read:test'])
        db.session.add(root)
        db.session.flush()
        child=Credential(application_id=application.id,organization_id=seeded_app.test_data['organization_id'],access_grant=grant,parent=root,root_id=root.id,name='Child',kind='CHILD',depth=1,secret_hash=hash_password('another-child-secret-2026'),secret_last4='2026',permissions=['read:test'])
        db.session.add(child)
        db.session.commit()
        root.status='FROZEN'
        db.session.commit()
        result=effective_status(child)
        assert result['allowed'] is False
        assert result['reason']=='ancestor_inactive'
        assert result['blocked_by']==root.id

def test_parent_credential_can_create_restricted_child(seeded_app):
    from datetime import datetime, timedelta, timezone
    from app.db import db
    from app.models import AccessGrant, Credential, Plan, Application
    from app.core.security import hash_password

    parent_secret='parent-secret-for-child-2026'
    with seeded_app.app_context():
        plan=Plan.query.filter_by(code='TEST').one()
        plan.max_children=1
        application=Application.query.get(seeded_app.test_data['application_id'])
        grant=AccessGrant(organization_id=seeded_app.test_data['organization_id'],application_id=application.id,plan_id=plan.id)
        parent=Credential(application_id=application.id,organization_id=seeded_app.test_data['organization_id'],access_grant=grant,name='Parent',kind='ROOT',depth=0,expires_at=datetime.now(timezone.utc)+timedelta(days=30),secret_hash=hash_password(parent_secret),secret_last4=parent_secret[-4:],permissions=['read:test','write:test'])
        db.session.add(parent)
        db.session.commit()
        parent_id=parent.id
    with seeded_app.test_client() as client:
        response=client.post('/api/v1/credentials/children',headers={'X-UECP-Application-Key':seeded_app.test_data['application_key']},json={'parent_credential':parent_secret,'name':'Child','expires_at':(datetime.now(timezone.utc)+timedelta(days=10)).isoformat(),'permissions':['read:test']})
        assert response.status_code==201
        assert response.json['parent_id']==parent_id
        assert response.json['permissions']==['read:test']

def test_expiry_pass_freezes_after_grace_and_deduplicates_notifications(seeded_app):
    from datetime import datetime, timedelta, timezone
    from app.db import db
    from app.models import AccessGrant, Credential, Plan, Application, NotificationLog
    from app.services.expiry import process_expirations
    from app.core.security import hash_password

    with seeded_app.app_context():
        plan=Plan.query.filter_by(code='TEST').one()
        application=Application.query.get(seeded_app.test_data['application_id'])
        application.owner_emails=['developer@example.test']
        grant=AccessGrant(organization_id=seeded_app.test_data['organization_id'],application_id=application.id,plan_id=plan.id,grace_days=2,expires_at=datetime.now(timezone.utc)-timedelta(days=3))
        credential=Credential(application_id=application.id,organization_id=seeded_app.test_data['organization_id'],access_grant=grant,name='Expired root',kind='ROOT',depth=0,secret_hash=hash_password('expired-secret-2026'),secret_last4='2026',permissions=['read:test'])
        db.session.add(credential)
        db.session.commit()
        first=process_expirations(datetime.now(timezone.utc))
        second=process_expirations(datetime.now(timezone.utc))
        assert first['credentials_frozen']==1
        assert second['notifications_created']==0
        assert credential.status=='FROZEN'
        assert grant.status=='FROZEN'
        assert NotificationLog.query.count()==1

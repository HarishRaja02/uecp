import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Integer, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from app.db import db

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)

class Organization(db.Model):
    __tablename__='organizations'
    id=db.Column(String(36), primary_key=True, default=uid)
    name=db.Column(String(200), nullable=False)
    status=db.Column(String(30), nullable=False, default='ACTIVE')
    created_at=db.Column(DateTime(timezone=True), nullable=False, default=now)
    memberships=relationship('Membership', cascade='all, delete-orphan')

class User(db.Model):
    __tablename__='users'
    id=db.Column(String(36), primary_key=True, default=uid)
    email=db.Column(String(320), unique=True, index=True, nullable=False)
    password_hash=db.Column(Text, nullable=False)
    status=db.Column(String(30), nullable=False, default='ACTIVE')
    is_platform_admin=db.Column(Boolean, nullable=False, default=False)
    mfa_enabled=db.Column(Boolean, nullable=False, default=False)
    created_at=db.Column(DateTime(timezone=True), nullable=False, default=now)
    memberships=relationship('Membership', cascade='all, delete-orphan')

class Membership(db.Model):
    __tablename__='organization_memberships'
    __table_args__=(UniqueConstraint('user_id','organization_id',name='uq_membership_user_org'),)
    id=db.Column(String(36), primary_key=True, default=uid)
    user_id=db.Column(ForeignKey('users.id'), nullable=False, index=True)
    organization_id=db.Column(ForeignKey('organizations.id'), nullable=False, index=True)
    role=db.Column(String(100), nullable=False, default='USER')

class Application(db.Model):
    __tablename__='applications'
    id=db.Column(String(36), primary_key=True, default=uid)
    name=db.Column(String(200), nullable=False)
    application_key_hash=db.Column(String(64), unique=True, index=True, nullable=False)
    application_key_last4=db.Column(String(4), nullable=False)
    status=db.Column(String(30), nullable=False, default='ACTIVE')
    capabilities=db.Column(JSON, nullable=False, default=dict)
    allowed_origins=db.Column(JSON, nullable=False, default=list)
    owner_emails=db.Column(JSON, nullable=False, default=list)
    created_at=db.Column(DateTime(timezone=True), nullable=False, default=now)

class Permission(db.Model):
    __tablename__='permissions'
    __table_args__=(UniqueConstraint('application_id','code',name='uq_app_permission'),)
    id=db.Column(String(36), primary_key=True, default=uid)
    application_id=db.Column(ForeignKey('applications.id'), nullable=False, index=True)
    code=db.Column(String(200), nullable=False)
    description=db.Column(Text, nullable=True)

class Role(db.Model):
    __tablename__='roles'
    __table_args__=(UniqueConstraint('organization_id','name',name='uq_role_org_name'),)
    id=db.Column(String(36), primary_key=True, default=uid)
    organization_id=db.Column(ForeignKey('organizations.id'), nullable=True, index=True)
    name=db.Column(String(100), nullable=False)
    description=db.Column(Text, nullable=True)
    is_system=db.Column(Boolean, nullable=False, default=False)

class RolePermission(db.Model):
    __tablename__='role_permissions'
    __table_args__=(UniqueConstraint('role_id','permission_id',name='uq_role_permission'),)
    id=db.Column(String(36), primary_key=True, default=uid)
    role_id=db.Column(ForeignKey('roles.id'), nullable=False, index=True)
    permission_id=db.Column(ForeignKey('permissions.id'), nullable=False, index=True)

class UserRole(db.Model):
    __tablename__='user_roles'
    __table_args__=(UniqueConstraint('user_id','role_id','organization_id',name='uq_user_role_scope'),)
    id=db.Column(String(36), primary_key=True, default=uid)
    user_id=db.Column(ForeignKey('users.id'), nullable=False, index=True)
    role_id=db.Column(ForeignKey('roles.id'), nullable=False, index=True)
    organization_id=db.Column(ForeignKey('organizations.id'), nullable=False, index=True)

class Plan(db.Model):
    __tablename__='plans'
    id=db.Column(String(36), primary_key=True, default=uid)
    code=db.Column(String(50), unique=True, nullable=False)
    name=db.Column(String(100), nullable=False)
    limits=db.Column(JSON, nullable=False, default=dict)
    features=db.Column(JSON, nullable=False, default=list)
    max_children=db.Column(Integer, nullable=False, default=10)
    max_depth=db.Column(Integer, nullable=False, default=4)
    default_term_days=db.Column(Integer, nullable=False, default=365)

class Subscription(db.Model):
    __tablename__='subscriptions'
    id=db.Column(String(36), primary_key=True, default=uid)
    organization_id=db.Column(ForeignKey('organizations.id'), nullable=False, index=True)
    plan_id=db.Column(ForeignKey('plans.id'), nullable=False)
    status=db.Column(String(30), nullable=False, default='ACTIVE')
    starts_at=db.Column(DateTime(timezone=True), nullable=False, default=now)
    expires_at=db.Column(DateTime(timezone=True), nullable=True)
    override_until=db.Column(DateTime(timezone=True), nullable=True)

class AccessGrant(db.Model):
    __tablename__='access_grants'
    __table_args__=(UniqueConstraint('organization_id','application_id',name='uq_access_grant_org_app'),)
    id=db.Column(String(36), primary_key=True, default=uid)
    organization_id=db.Column(ForeignKey('organizations.id'), nullable=False, index=True)
    application_id=db.Column(ForeignKey('applications.id'), nullable=False, index=True)
    plan_id=db.Column(ForeignKey('plans.id'), nullable=False, index=True)
    status=db.Column(String(30), nullable=False, default='ACTIVE')
    starts_at=db.Column(DateTime(timezone=True), nullable=False, default=now)
    expires_at=db.Column(DateTime(timezone=True), nullable=True)
    grace_days=db.Column(Integer, nullable=False, default=0)
    frozen_reason=db.Column(Text, nullable=True)
    created_at=db.Column(DateTime(timezone=True), nullable=False, default=now)
    credentials=relationship('Credential', back_populates='access_grant', cascade='all, delete-orphan')

class Session(db.Model):
    __tablename__='sessions'
    id=db.Column(String(36), primary_key=True, default=uid)
    user_id=db.Column(ForeignKey('users.id'), nullable=False, index=True)
    organization_id=db.Column(ForeignKey('organizations.id'), nullable=False, index=True)
    refresh_token_hash=db.Column(Text, nullable=False)
    ip=db.Column(String(64), nullable=True)
    user_agent=db.Column(Text, nullable=True)
    revoked=db.Column(Boolean, nullable=False, default=False)
    created_at=db.Column(DateTime(timezone=True), nullable=False, default=now)
    expires_at=db.Column(DateTime(timezone=True), nullable=False)
    last_seen_at=db.Column(DateTime(timezone=True), nullable=False, default=now)

class FeatureFlag(db.Model):
    __tablename__='feature_flags'
    __table_args__=(UniqueConstraint('application_id','key','organization_id',name='uq_feature_scope'),)
    id=db.Column(String(36), primary_key=True, default=uid)
    application_id=db.Column(ForeignKey('applications.id'), nullable=False, index=True)
    organization_id=db.Column(ForeignKey('organizations.id'), nullable=True, index=True)
    key=db.Column(String(150), nullable=False)
    enabled=db.Column(Boolean, nullable=False, default=False)
    environment=db.Column(String(30), nullable=True)
    rollout_percent=db.Column(Integer, nullable=False, default=100)

class UsageRecord(db.Model):
    __tablename__='usage_records'
    id=db.Column(String(36), primary_key=True, default=uid)
    organization_id=db.Column(ForeignKey('organizations.id'), nullable=False, index=True)
    application_id=db.Column(ForeignKey('applications.id'), nullable=True, index=True)
    metric=db.Column(String(100), nullable=False)
    quantity=db.Column(db.Numeric(20,4), nullable=False, default=0)
    period_start=db.Column(DateTime(timezone=True), nullable=False, default=now)
    created_at=db.Column(DateTime(timezone=True), nullable=False, default=now)

class AuditEvent(db.Model):
    __tablename__='audit_events'
    id=db.Column(String(36), primary_key=True, default=uid)
    timestamp=db.Column(DateTime(timezone=True), nullable=False, default=now, index=True)
    actor_id=db.Column(String(36), nullable=True)
    actor_type=db.Column(String(50), nullable=False, default='USER')
    organization_id=db.Column(String(36), nullable=True, index=True)
    application_id=db.Column(String(36), nullable=True)
    action=db.Column(String(120), nullable=False)
    resource=db.Column(String(120), nullable=False)
    resource_id=db.Column(String(200), nullable=True)
    result=db.Column(String(30), nullable=False)
    reason=db.Column(Text, nullable=True)
    ip=db.Column(String(64), nullable=True)
    user_agent=db.Column(Text, nullable=True)
    request_id=db.Column(String(100), nullable=True, index=True)
    correlation_id=db.Column(String(100), nullable=True)
    metadata_json=db.Column(JSON, nullable=False, default=dict)

class SecurityEvent(db.Model):
    __tablename__='security_events'
    id=db.Column(String(36), primary_key=True, default=uid)
    timestamp=db.Column(DateTime(timezone=True), nullable=False, default=now, index=True)
    severity=db.Column(String(20), nullable=False)
    event_type=db.Column(String(120), nullable=False)
    organization_id=db.Column(String(36), nullable=True, index=True)
    user_id=db.Column(String(36), nullable=True, index=True)
    ip=db.Column(String(64), nullable=True)
    details=db.Column(JSON, nullable=False, default=dict)
    resolved=db.Column(Boolean, nullable=False, default=False)

class Credential(db.Model):
    __tablename__='credentials'
    id=db.Column(String(36), primary_key=True, default=uid)
    application_id=db.Column(ForeignKey('applications.id'), nullable=False, index=True)
    organization_id=db.Column(ForeignKey('organizations.id'), nullable=True, index=True)
    access_grant_id=db.Column(ForeignKey('access_grants.id'), nullable=True, index=True)
    parent_id=db.Column(ForeignKey('credentials.id'), nullable=True, index=True)
    root_id=db.Column(ForeignKey('credentials.id'), nullable=True, index=True)
    name=db.Column(String(150), nullable=False)
    kind=db.Column(String(20), nullable=False, default='ROOT')
    path=db.Column(String(1000), nullable=True)
    depth=db.Column(Integer, nullable=False, default=0)
    secret_hash=db.Column(Text, nullable=True)
    legacy_secret_ciphertext=db.Column('secret_ciphertext', Text, nullable=True, default='')
    secret_last4=db.Column(String(4), nullable=False)
    status=db.Column(String(30), nullable=False, default='ACTIVE')
    expires_at=db.Column(DateTime(timezone=True), nullable=True)
    frozen_at=db.Column(DateTime(timezone=True), nullable=True)
    frozen_reason=db.Column(Text, nullable=True)
    permissions=db.Column(JSON, nullable=False, default=list)
    last_used_at=db.Column(DateTime(timezone=True), nullable=True)
    created_at=db.Column(DateTime(timezone=True), nullable=False, default=now)
    access_grant=relationship('AccessGrant', back_populates='credentials')
    parent=relationship('Credential', remote_side=[id], foreign_keys=[parent_id], back_populates='children')
    children=relationship('Credential', foreign_keys=[parent_id], back_populates='parent')

class NotificationRule(db.Model):
    __tablename__='notification_rules'
    __table_args__=(UniqueConstraint('access_grant_id','event_type','days_before',name='uq_notification_rule_event'),)
    id=db.Column(String(36), primary_key=True, default=uid)
    access_grant_id=db.Column(ForeignKey('access_grants.id'), nullable=False, index=True)
    event_type=db.Column(String(50), nullable=False)
    days_before=db.Column(Integer, nullable=False, default=0)
    enabled=db.Column(Boolean, nullable=False, default=True)
    recipients=db.Column(JSON, nullable=False, default=list)
    created_at=db.Column(DateTime(timezone=True), nullable=False, default=now)

class NotificationLog(db.Model):
    __tablename__='notification_log'
    __table_args__=(UniqueConstraint('notification_key',name='uq_notification_log_key'),)
    id=db.Column(String(36), primary_key=True, default=uid)
    notification_key=db.Column(String(300), nullable=False)
    access_grant_id=db.Column(ForeignKey('access_grants.id'), nullable=True, index=True)
    credential_id=db.Column(ForeignKey('credentials.id'), nullable=True, index=True)
    event_type=db.Column(String(50), nullable=False)
    recipient=db.Column(String(320), nullable=False)
    status=db.Column(String(30), nullable=False, default='PENDING')
    attempts=db.Column(Integer, nullable=False, default=0)
    last_error=db.Column(Text, nullable=True)
    sent_at=db.Column(DateTime(timezone=True), nullable=True)
    created_at=db.Column(DateTime(timezone=True), nullable=False, default=now)

class Webhook(db.Model):
    __tablename__='webhooks'
    id=db.Column(String(36), primary_key=True, default=uid)
    application_id=db.Column(ForeignKey('applications.id'), nullable=False, index=True)
    endpoint=db.Column(String(1000), nullable=False)
    secret_ciphertext=db.Column(Text, nullable=False)
    active=db.Column(Boolean, nullable=False, default=True)
    created_at=db.Column(DateTime(timezone=True), nullable=False, default=now)

class SecurityPolicy(db.Model):
    __tablename__='security_policies'
    id=db.Column(String(36), primary_key=True, default=uid)
    organization_id=db.Column(ForeignKey('organizations.id'), nullable=True, index=True)
    name=db.Column(String(150), nullable=False)
    rules=db.Column(JSON, nullable=False, default=dict)
    enabled=db.Column(Boolean, nullable=False, default=True)
    updated_at=db.Column(DateTime(timezone=True), nullable=False, default=now, onupdate=now)

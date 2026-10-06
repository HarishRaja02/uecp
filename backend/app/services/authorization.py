from datetime import datetime, timezone
from app.models import Membership, Organization, Subscription, Plan
from app.core.time import as_utc

def get_membership(user_id, organization_id):
    return Membership.query.filter_by(user_id=user_id, organization_id=organization_id).first()

def subscription_active(organization_id):
    sub=Subscription.query.filter_by(organization_id=organization_id).order_by(Subscription.starts_at.desc()).first()
    if not sub: return False
    if sub.status in {'SUSPENDED','EXPIRED','CANCELLED','PAST_DUE'}: return False
    now=datetime.now(timezone.utc)
    if sub.expires_at and as_utc(sub.expires_at) < now and not (sub.override_until and as_utc(sub.override_until) > now): return False
    return True

def organization_active(organization_id):
    organization = Organization.query.get(organization_id)
    return bool(organization and organization.status == 'ACTIVE')

def authorize(user, organization_id, required_role=None):
    if user.is_platform_admin: return True
    if not organization_active(organization_id) or user.status != 'ACTIVE': return False
    if not get_membership(user.id, organization_id): return False
    if not subscription_active(organization_id): return False
    if required_role:
        m=get_membership(user.id, organization_id)
        return m.role in {required_role,'ORGANIZATION_ADMIN','MANAGER'}
    return True

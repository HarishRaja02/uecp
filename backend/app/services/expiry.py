from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import smtplib

from app.core.config import settings
from app.core.time import as_utc
from app.db import db
from app.models import AccessGrant, Application, Credential, Membership, NotificationLog, NotificationRule, Organization, User


REMINDER_DAYS = (30, 14, 7, 3, 1)


def _now():
    return datetime.now(timezone.utc)


def _recipients(grant, application):
    recipients = set(application.owner_emails or [])
    memberships = Membership.query.filter_by(organization_id=grant.organization_id).all()
    admin_ids = [item.user_id for item in memberships if item.role in {'OWNER', 'ORGANIZATION_ADMIN', 'SUPER_ADMIN'}]
    if admin_ids:
        recipients.update(user.email for user in User.query.filter(User.id.in_(admin_ids)).all())
    return sorted(email.strip().lower() for email in recipients if isinstance(email, str) and email.strip())


def _log_once(grant, credential, event_type, days_before, recipient):
    key = f'{grant.id}:{credential.id if credential else "grant"}:{event_type}:{days_before}:{recipient}'
    if NotificationLog.query.filter_by(notification_key=key).first():
        return False
    db.session.add(NotificationLog(
        notification_key=key,
        access_grant_id=grant.id,
        credential_id=credential.id if credential else None,
        event_type=event_type,
        recipient=recipient,
        status='PENDING',
    ))
    return True


def process_expirations(now=None):
    now = now or _now()
    created_notifications = 0
    frozen_credentials = 0
    grants = AccessGrant.query.filter(AccessGrant.status.in_(['ACTIVE', 'GRACE'])).all()
    for grant in grants:
        application = Application.query.get(grant.application_id)
        organization = Organization.query.get(grant.organization_id)
        if not application or not organization:
            continue
        recipients = _recipients(grant, application)
        rules = NotificationRule.query.filter_by(access_grant_id=grant.id, enabled=True).all()
        if not rules:
            rules = [NotificationRule(event_type='EXPIRY_REMINDER', days_before=days, recipients=recipients) for days in REMINDER_DAYS]
        for credential in grant.credentials:
            expiry = credential.expires_at or grant.expires_at
            if not expiry:
                continue
            expiry = as_utc(expiry)
            remaining = expiry - now
            for rule in rules:
                if rule.event_type != 'EXPIRY_REMINDER' or remaining > timedelta(days=rule.days_before) or remaining < timedelta(days=max(rule.days_before - 1, 0)):
                    continue
                targets = rule.recipients or recipients
                for recipient in targets:
                    created_notifications += int(_log_once(grant, credential, rule.event_type, rule.days_before, recipient))
            grace_until = expiry + timedelta(days=max(grant.grace_days or 0, 0))
            if now > expiry and now <= grace_until:
                if credential.status not in {'FROZEN', 'REVOKED'}:
                    credential.status = 'GRACE'
                    created_notifications += sum(_log_once(grant, credential, 'GRACE_STARTED', 0, recipient) for recipient in recipients)
            elif now > grace_until:
                if credential.status not in {'FROZEN', 'REVOKED'}:
                    credential.status = 'FROZEN'
                    credential.frozen_at = now
                    credential.frozen_reason = 'expired'
                    frozen_credentials += 1
                    created_notifications += sum(_log_once(grant, credential, 'EXPIRED', 0, recipient) for recipient in recipients)
        if grant.expires_at and now > as_utc(grant.expires_at) + timedelta(days=max(grant.grace_days or 0, 0)):
            grant.status = 'FROZEN'
            grant.frozen_reason = 'expired'
    db.session.commit()
    return {'notifications_created': created_notifications, 'credentials_frozen': frozen_credentials}


def deliver_pending_notifications(limit=100):
    if not settings.smtp_host or not settings.smtp_from:
        raise RuntimeError('SMTP_HOST and SMTP_FROM must be configured to deliver notifications')
    pending = NotificationLog.query.filter(NotificationLog.status.in_(['PENDING', 'FAILED'])).order_by(NotificationLog.created_at.asc()).limit(limit).all()
    delivered = 0
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        for notification in pending:
            message = EmailMessage()
            message['Subject'] = f'UECP credential notification: {notification.event_type}'
            message['From'] = settings.smtp_from
            message['To'] = notification.recipient
            message.set_content(f'UECP notification {notification.event_type} was generated for credential access.')
            notification.attempts += 1
            try:
                server.send_message(message)
            except smtplib.SMTPException as exc:
                notification.status = 'FAILED'
                notification.last_error = str(exc)
                continue
            notification.status = 'SENT'
            notification.sent_at = _now()
            notification.last_error = None
            delivered += 1
    db.session.commit()
    return {'delivered': delivered, 'remaining': len(pending) - delivered}

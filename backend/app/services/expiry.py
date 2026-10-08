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
            contact = settings.smtp_from or 'support@uecp.local'
            message.set_content(
                f"UECP notification {notification.event_type} was generated for credential access.\n\n"
                f"To renew or reactivate your subscription, please reach out to: {contact}"
            )
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


def send_credential_reminder(credential, recipient=None, contact_email=None, note=None):
    from app.models import Application, AccessGrant
    app = Application.query.get(credential.application_id)
    grant = AccessGrant.query.get(credential.access_grant_id) if credential.access_grant_id else None
    app_name = app.name if app else 'Client Application'

    # Determine recipient
    if not recipient:
        if app and app.owner_emails:
            recipient = app.owner_emails[0]
        else:
            recipients = _recipients(grant, app) if (grant and app) else []
            recipient = recipients[0] if recipients else None

    if not recipient:
        raise ValueError('No client email found. Please provide or configure a client email.')

    recipient = str(recipient).strip().lower()
    contact = contact_email or settings.smtp_from or 'support@uecp.local'

    expiry = credential.expires_at or (grant.expires_at if grant else None)
    now_dt = _now()

    if expiry:
        expiry_dt = as_utc(expiry)
        expiry_str = expiry_dt.strftime('%B %d, %Y at %H:%M:%S UTC')
        diff = expiry_dt - now_dt
        if diff.total_seconds() > 0:
            days = diff.days
            hours = int((diff.seconds // 3600))
            time_left_str = f"{days} days, {hours} hours remaining" if days > 0 else f"{hours} hours remaining"
        else:
            time_left_str = "EXPIRED"
    else:
        expiry_str = "No Expiration Configured"
        time_left_str = "Indefinite"

    subject = f"[Action Required] Subscription Expiration Notice: {app_name}"

    text_content = f"""Dear Client,

This is an official expiration notice regarding your access subscription for {app_name}.

--- CREDENTIAL & SUBSCRIPTION STATUS ---
• Application: {app_name}
• Credential Name: {credential.name} ({credential.kind})
• Current Status: {credential.status}
• Expiration Date: {expiry_str}
• Time Remaining: {time_left_str}

--- REACTIVATION & RENEWAL INSTRUCTIONS ---
Your client application access is scheduled to expire. Once expired, client API validation checks will be blocked automatically.

To reactivate your subscription or request an extension, please contact our administration team:
Reach out to: {contact}

{f"Admin Note: {note}" if note else ""}

Thank you,
Universal Enterprise Control Plane (UECP) Administration Team
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #080b12; color: #f8fafc; margin: 0; padding: 24px; }}
    .card {{ max-width: 580px; margin: 0 auto; background: #0e1524; border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 28px; box-shadow: 0 16px 40px rgba(0,0,0,0.6); }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); }}
    .title {{ font-size: 20px; font-weight: 700; margin: 16px 0 8px; color: #ffffff; }}
    .lead {{ color: #94a3b8; font-size: 14px; line-height: 1.5; margin-bottom: 20px; }}
    .info-table {{ width: 100%; border-collapse: collapse; margin: 16px 0 24px; background: rgba(0,0,0,0.2); border-radius: 8px; overflow: hidden; }}
    .info-table td {{ padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 13px; }}
    .info-table tr:last-child td {{ border-bottom: none; }}
    .info-label {{ color: #94a3b8; font-weight: 600; width: 40%; }}
    .info-val {{ color: #f8fafc; }}
    .reachout-box {{ background: rgba(0, 145, 255, 0.08); border: 1px solid rgba(0, 145, 255, 0.3); border-radius: 10px; padding: 18px; margin: 20px 0; }}
    .reachout-title {{ font-size: 12px; font-weight: 700; color: #0091ff; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
    .reachout-text {{ font-size: 13px; line-height: 1.5; color: #f8fafc; margin-bottom: 10px; }}
    .contact-email {{ display: inline-block; font-size: 15px; font-weight: 700; color: #0091ff; text-decoration: none; padding: 6px 12px; background: rgba(0, 145, 255, 0.15); border-radius: 6px; }}
    .footer {{ font-size: 11px; color: #64748b; margin-top: 24px; text-align: center; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">Expiration Warning</span>
    <h2 class="title">Subscription & Access Notice</h2>
    <p class="lead">
      Your client application credentials for <strong>{app_name}</strong> are approaching expiration. Please review your subscription timeline below:
    </p>

    <table class="info-table">
      <tr><td class="info-label">Application</td><td class="info-val"><strong>{app_name}</strong></td></tr>
      <tr><td class="info-label">Credential</td><td class="info-val">{credential.name} <code style="color:#0091ff;">({credential.kind})</code></td></tr>
      <tr><td class="info-label">Current Status</td><td class="info-val">{credential.status}</td></tr>
      <tr><td class="info-label">Expiration Date</td><td class="info-val"><strong>{expiry_str}</strong></td></tr>
      <tr><td class="info-label">Time Remaining</td><td class="info-val"><strong style="color:#f59e0b;">{time_left_str}</strong></td></tr>
    </table>

    <div class="reachout-box">
      <div class="reachout-title">How to Reactivate / Renew Subscription</div>
      <div class="reachout-text">
        To avoid access cutoff or reactivate an expired subscription, please contact our administration team:
      </div>
      <div>
        <a href="mailto:{contact}?subject=Subscription%20Reactivation%20Request%20-%20{app_name}" class="contact-email">✉ {contact}</a>
      </div>
    </div>

    {f"<p style='color:#94a3b8; font-size:12px; margin-top:12px;'><em>Admin Note: {note}</em></p>" if note else ""}

    <div class="footer">
      Universal Enterprise Control Plane (UECP) • Automated Credential Governance
    </div>
  </div>
</body>
</html>
"""

    smtp_enabled = bool(settings.smtp_host and settings.smtp_from)
    status = 'PENDING'
    last_error = None

    if smtp_enabled:
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
                server.starttls()
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password)
                msg = EmailMessage()
                msg['Subject'] = subject
                msg['From'] = settings.smtp_from
                msg['To'] = recipient
                msg.set_content(text_content)
                msg.add_alternative(html_content, subtype='html')
                server.send_message(msg)
                status = 'SENT'
        except Exception as exc:
            status = 'FAILED'
            last_error = str(exc)
    else:
        # Development / test mode fallback
        status = 'SIMULATED'
        last_error = 'SMTP not configured in environment; notification recorded and simulated in dev mode.'

    import time
    log_key = f"manual:{credential.id}:{int(time.time())}:{recipient}"
    log_entry = NotificationLog(
        notification_key=log_key,
        access_grant_id=credential.access_grant_id,
        credential_id=credential.id,
        event_type='EXPIRY_REMINDER_MANUAL',
        recipient=recipient,
        status=status,
        attempts=1,
        last_error=last_error if status == 'FAILED' else None,
        sent_at=now_dt if status in {'SENT', 'SIMULATED'} else None,
    )
    db.session.add(log_entry)
    db.session.commit()

    return {
        'ok': True,
        'recipient': recipient,
        'status': status,
        'smtp_configured': smtp_enabled,
        'message': f"Reminder sent to {recipient}" if status == 'SENT' else f"Reminder recorded for {recipient} (Simulated - SMTP not configured in .env)",
        'sent_at': now_dt.isoformat(),
        'contact_email': contact,
        'time_remaining': time_left_str,
        'expires_at': expiry.isoformat() if expiry else None,
    }


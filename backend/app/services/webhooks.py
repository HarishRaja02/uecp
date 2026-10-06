import base64
import hashlib
import hmac
import json
import urllib.request
from datetime import datetime, timezone

from cryptography.fernet import Fernet

from app.core.config import settings


def _cipher():
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.flask_secret_key.encode()).digest())
    return Fernet(key)


def protect_secret(secret):
    return _cipher().encrypt(secret.encode()).decode()


def reveal_secret(ciphertext):
    return _cipher().decrypt(ciphertext.encode()).decode()


def signature(secret, timestamp, body):
    payload = f'{timestamp}.{body}'.encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def deliver(webhook, event_type, data, timeout=10):
    body = json.dumps({
        'id': data.get('event_id'),
        'type': event_type,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'data': data,
    }, separators=(',', ':'), sort_keys=True)
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    secret = reveal_secret(webhook.secret_ciphertext)
    request = urllib.request.Request(
        webhook.endpoint,
        data=body.encode(),
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'UECP-Webhook/1',
            'X-UECP-Timestamp': timestamp,
            'X-UECP-Signature': f'v1={signature(secret, timestamp, body)}',
            'X-UECP-Event': event_type,
        },
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f'webhook returned HTTP {response.status}')
    return True

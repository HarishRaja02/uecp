from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_urlsafe
from hashlib import sha256
from jose import jwt, JWTError
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from app.core.config import settings

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
class SecurityError(Exception): pass

def hash_password(password: str) -> str:
    if len(password) < 12: raise SecurityError('Password must contain at least 12 characters')
    return ph.hash(password)

def verify_password(password: str, encoded: str) -> bool:
    try: return ph.verify(encoded, password)
    except (VerifyMismatchError, VerificationError): return False

_ephemeral_priv = None
_ephemeral_pub = None

def _get_ephemeral_keys():
    global _ephemeral_priv, _ephemeral_pub
    if _ephemeral_priv is None:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _ephemeral_priv = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        _ephemeral_pub = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    return _ephemeral_priv, _ephemeral_pub

def load_key(path, env_var=None):
    import os
    if env_var:
        val = os.getenv(env_var)
        if val:
            return val.replace('\\n', '\n')
    p = Path(path)
    if p.exists():
        return p.read_text(encoding='utf-8')
    priv, pub = _get_ephemeral_keys()
    if (env_var and 'PRIVATE' in env_var) or 'private' in str(path).lower():
        return priv
    return pub

def create_access_token(subject, tenant_id, roles, session_id):
    now=datetime.now(timezone.utc)
    payload={'sub':subject,'tenant_id':tenant_id,'roles':roles,'sid':session_id,'iss':settings.issuer,'aud':settings.audience,'iat':now,'nbf':now,'exp':now+timedelta(minutes=settings.access_token_minutes),'jti':token_urlsafe(18),'typ':'access'}
    return jwt.encode(payload, load_key(settings.jwt_private_key_path, 'JWT_PRIVATE_KEY'), algorithm=settings.jwt_algorithm)

def decode_access_token(token):
    try:
        return jwt.decode(token,load_key(settings.jwt_public_key_path, 'JWT_PUBLIC_KEY'),algorithms=[settings.jwt_algorithm],issuer=settings.issuer,audience=settings.audience,options={'require_exp':True,'require_iat':True,'require_nbf':True})
    except JWTError as exc: raise SecurityError('Invalid or expired access token') from exc

def new_refresh_token(): return token_urlsafe(64)
def hash_token(token): return sha256(token.encode()).hexdigest()

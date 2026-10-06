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

def load_key(path):
    p=Path(path)
    if not p.exists(): raise SecurityError(f'Missing required security key: {p}')
    return p.read_text(encoding='utf-8')

def create_access_token(subject, tenant_id, roles, session_id):
    now=datetime.now(timezone.utc)
    payload={'sub':subject,'tenant_id':tenant_id,'roles':roles,'sid':session_id,'iss':settings.issuer,'aud':settings.audience,'iat':now,'nbf':now,'exp':now+timedelta(minutes=settings.access_token_minutes),'jti':token_urlsafe(18),'typ':'access'}
    return jwt.encode(payload, load_key(settings.jwt_private_key_path), algorithm=settings.jwt_algorithm)

def decode_access_token(token):
    try:
        return jwt.decode(token,load_key(settings.jwt_public_key_path),algorithms=[settings.jwt_algorithm],issuer=settings.issuer,audience=settings.audience,options={'require_exp':True,'require_iat':True,'require_nbf':True})
    except JWTError as exc: raise SecurityError('Invalid or expired access token') from exc

def new_refresh_token(): return token_urlsafe(64)
def hash_token(token): return sha256(token.encode()).hexdigest()

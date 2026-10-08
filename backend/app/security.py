import time
from functools import wraps
from datetime import datetime, timezone
from flask import request, jsonify, g
from app.core.security import decode_access_token, SecurityError
from app.core.time import as_utc
from app.models import User, Session

_PRINCIPAL_CACHE = {}
_CACHE_TTL = 30.0

def invalidate_auth_cache(user_id=None, session_id=None):
    global _PRINCIPAL_CACHE
    if not user_id and not session_id:
        _PRINCIPAL_CACHE.clear()
        return
    to_delete = []
    for k, v in _PRINCIPAL_CACHE.items():
        if (user_id and v.get('user_id') == user_id) or (session_id and v.get('session_id') == session_id):
            to_delete.append(k)
    for k in to_delete:
        _PRINCIPAL_CACHE.pop(k, None)

class CachedUser:
    __slots__ = ('id', 'email', 'status', 'is_platform_admin', 'mfa_enabled', 'created_at')
    def __init__(self, id, email, status, is_platform_admin, mfa_enabled=False, created_at=None):
        self.id = id
        self.email = email
        self.status = status
        self.is_platform_admin = bool(is_platform_admin)
        self.mfa_enabled = bool(mfa_enabled)
        self.created_at = created_at

class CachedSession:
    __slots__ = ('id', 'user_id', 'revoked', 'expires_at')
    def __init__(self, id, user_id, revoked, expires_at):
        self.id = id
        self.user_id = user_id
        self.revoked = bool(revoked)
        self.expires_at = expires_at

def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return jsonify(error='unauthorized', message='Authentication required'), 401
        try:
            claims = decode_access_token(header[7:])
        except SecurityError:
            return jsonify(error='unauthorized', message='Invalid or expired token'), 401

        sub = claims.get('sub')
        sid = claims.get('sid')
        cache_key = f"{sub}:{sid}"
        now = time.time()

        cached = _PRINCIPAL_CACHE.get(cache_key)
        if cached and (now - cached['time'] < _CACHE_TTL):
            user = cached['user']
            session = cached['session']
        else:
            from app.db import db
            res = db.session.query(User, Session).join(Session, Session.user_id == User.id).filter(User.id == sub, Session.id == sid).first()
            user, session = res if res else (None, None)
            if not user or user.status != 'ACTIVE' or not session or session.revoked or as_utc(session.expires_at) < datetime.now(timezone.utc):
                _PRINCIPAL_CACHE.pop(cache_key, None)
                return jsonify(error='unauthorized', message='Session is no longer valid'), 401
            cached_user = CachedUser(
                id=user.id,
                email=user.email,
                status=user.status,
                is_platform_admin=user.is_platform_admin,
                mfa_enabled=user.mfa_enabled,
                created_at=user.created_at,
            )
            cached_session = CachedSession(
                id=session.id,
                user_id=session.user_id,
                revoked=session.revoked,
                expires_at=session.expires_at,
            )
            _PRINCIPAL_CACHE[cache_key] = {
                'time': now,
                'user': cached_user,
                'session': cached_session,
                'user_id': user.id,
                'session_id': session.id,
            }
            user = cached_user
            session = cached_session

        g.principal = {'user': user, 'claims': claims, 'session': session}
        return fn(*args, **kwargs)
    return wrapper

def platform_admin(fn):
    @wraps(fn)
    @auth_required
    def wrapper(*args, **kwargs):
        if not g.principal['user'].is_platform_admin:
            return jsonify(error='forbidden', message='Platform administrator privileges required'), 403
        return fn(*args, **kwargs)
    return wrapper

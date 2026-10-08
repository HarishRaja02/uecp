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

        t_auth0 = time.time()
        sub = claims.get('sub')
        sid = claims.get('sid')
        cache_key = f"{sub}:{sid}"
        now = time.time()

        cached = _PRINCIPAL_CACHE.get(cache_key)
        if cached and (now - cached['time'] < _CACHE_TTL):
            user = cached['user']
            session = cached['session']
            print(f">>> [AUTH] Cache HIT in {time.time()-t_auth0:.4f}s")
        else:
            user = User.query.get(sub)
            session = Session.query.get(sid)
            if not user or user.status != 'ACTIVE' or not session or session.revoked or as_utc(session.expires_at) < datetime.now(timezone.utc):
                _PRINCIPAL_CACHE.pop(cache_key, None)
                return jsonify(error='unauthorized', message='Session is no longer valid'), 401
            _PRINCIPAL_CACHE[cache_key] = {
                'time': now,
                'user': user,
                'session': session,
                'user_id': user.id,
                'session_id': session.id,
            }
            print(f">>> [AUTH] Cache MISS (DB fetched) in {time.time()-t_auth0:.4f}s")

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

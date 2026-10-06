from functools import wraps
from datetime import datetime, timezone
from flask import request, jsonify, g
from app.core.security import decode_access_token, SecurityError
from app.core.time import as_utc
from app.models import User, Session

def auth_required(fn):
    @wraps(fn)
    def wrapper(*args,**kwargs):
        header=request.headers.get('Authorization','')
        if not header.startswith('Bearer '): return jsonify(error='unauthorized',message='Authentication required'),401
        try: claims=decode_access_token(header[7:])
        except SecurityError: return jsonify(error='unauthorized',message='Invalid or expired token'),401
        user=User.query.get(claims.get('sub')); session=Session.query.get(claims.get('sid'))
        if not user or user.status!='ACTIVE' or not session or session.revoked or as_utc(session.expires_at) < datetime.now(timezone.utc):
            return jsonify(error='unauthorized',message='Session is no longer valid'),401
        g.principal={'user':user,'claims':claims,'session':session}
        return fn(*args,**kwargs)
    return wrapper

def platform_admin(fn):
    @wraps(fn)
    @auth_required
    def wrapper(*args,**kwargs):
        if not g.principal['user'].is_platform_admin: return jsonify(error='forbidden',message='Platform administrator privileges required'),403
        return fn(*args,**kwargs)
    return wrapper

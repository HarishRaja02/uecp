import os
import socket
import urllib.parse
from flask import Blueprint, jsonify, request

health_bp = Blueprint('health', __name__)

_DNS_CACHE = None
_TABLES_CACHE = None

@health_bp.get('/health')
def health():
    global _DNS_CACHE, _TABLES_CACHE
    db_raw = os.getenv('DATABASE_URL', '')
    parsed = urllib.parse.urlparse(db_raw) if db_raw else None

    if _DNS_CACHE is None and parsed and parsed.hostname:
        dns_info = {'hostname': parsed.hostname, 'port': parsed.port or 5432}
        try:
            dns_info['ipv4'] = socket.gethostbyname(parsed.hostname)
        except Exception as e:
            dns_info['ipv4_error'] = f"{type(e).__name__}: {e}"
        _DNS_CACHE = dns_info
    dns_info = _DNS_CACHE or {}

    db_status = 'ok'
    tables = _TABLES_CACHE or []
    try:
        from app.db import db
        from sqlalchemy import text
        with db.engine.connect() as conn:
            val = conn.execute(text("SELECT 1")).scalar()
            db_status = f"connected (select 1 = {val})"
        if not _TABLES_CACHE:
            from sqlalchemy import inspect
            _TABLES_CACHE = inspect(db.engine).get_table_names()
            tables = _TABLES_CACHE
    except Exception as e:
        db_status = f"{type(e).__name__}: {str(e)}"

    return jsonify(
        status='ok',
        service='uecp-api',
        version='1.0.3',
        database={
            'configured': bool(db_raw),
            'scheme': parsed.scheme if parsed else 'none',
            'host': parsed.hostname if parsed else 'none',
            'port': parsed.port if parsed else 'none',
            'dns': dns_info,
            'status': db_status,
            'tables': tables
        }
    )


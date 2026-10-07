import os
import socket
import urllib.parse
from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)

@health_bp.get('/health')
def health():
    db_raw = os.getenv('DATABASE_URL', '')
    parsed = urllib.parse.urlparse(db_raw) if db_raw else None

    dns_info = {}
    if parsed and parsed.hostname:
        dns_info['hostname'] = parsed.hostname
        dns_info['port'] = parsed.port or 5432
        try:
            dns_info['ipv4'] = socket.gethostbyname(parsed.hostname)
        except Exception as e:
            dns_info['ipv4_error'] = f"{type(e).__name__}: {e}"

        try:
            addr_info = socket.getaddrinfo(parsed.hostname, parsed.port or 5432, socket.AF_INET, socket.SOCK_STREAM)
            dns_info['getaddrinfo_ipv4'] = [item[4][0] for item in addr_info]
        except Exception as e:
            dns_info['getaddrinfo_ipv4_error'] = f"{type(e).__name__}: {e}"

        try:
            addr_all = socket.getaddrinfo(parsed.hostname, parsed.port or 5432, 0, socket.SOCK_STREAM)
            dns_info['getaddrinfo_all'] = [item[4][0] for item in addr_all]
        except Exception as e:
            dns_info['getaddrinfo_all_error'] = f"{type(e).__name__}: {e}"

    db_status = 'ok'
    tables = []
    try:
        from app.db import db
        from sqlalchemy import text
        with db.engine.connect() as conn:
            val = conn.execute(text("SELECT 1")).scalar()
            db_status = f"connected (select 1 = {val})"
        from sqlalchemy import inspect
        tables = inspect(db.engine).get_table_names()
    except Exception as e:
        db_status = f"{type(e).__name__}: {str(e)}"

    return jsonify(
        status='ok',
        service='uecp-api',
        version='1.0.2',
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


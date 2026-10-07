from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)

@health_bp.get('/health')
def health():
    db_status = 'ok'
    tables = []
    try:
        from app.db import db
        from sqlalchemy import inspect
        tables = inspect(db.engine).get_table_names()
    except Exception as e:
        db_status = str(e)
    return jsonify(
        status='ok',
        service='uecp-api',
        version='1.0.1',
        database={
            'status': db_status,
            'tables': tables
        }
    )

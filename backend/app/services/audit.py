from uuid import uuid4
from flask import request
from app.db import db
from app.models import AuditEvent, SecurityEvent

def audit(actor_id=None, organization_id=None, action='', resource='', result='SUCCESS', resource_id=None, reason=None, application_id=None, metadata=None):
    event=AuditEvent(actor_id=actor_id,organization_id=organization_id,action=action,resource=resource,result=result,resource_id=resource_id,reason=reason,application_id=application_id,ip=request.remote_addr,user_agent=request.headers.get('User-Agent','')[:1000],request_id=request.headers.get('X-Request-ID',str(uuid4())),correlation_id=request.headers.get('X-Correlation-ID'),metadata_json=metadata or {})
    db.session.add(event)
    return event

def security_event(severity,event_type,user_id=None,organization_id=None,details=None):
    db.session.add(SecurityEvent(severity=severity,event_type=event_type,user_id=user_id,organization_id=organization_id,ip=request.remote_addr,details=details or {}))

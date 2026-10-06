from app import create_app
from app.db import db
from app.models import *
from app.core.security import hash_password
from alembic import command
from alembic.config import Config
from pathlib import Path
import os

app=create_app()
with app.app_context():
    admin_password=os.getenv('SEED_ADMIN_PASSWORD')
    if not admin_password:
        raise RuntimeError('SEED_ADMIN_PASSWORD must be set before seeding')
    project_root = Path(__file__).resolve().parents[1]
    migration_config=Config(str(project_root / 'alembic.ini'))
    migration_config.set_main_option('script_location', str(project_root / 'alembic'))
    migration_config.set_main_option('sqlalchemy.url', app.config['SQLALCHEMY_DATABASE_URI'])
    command.upgrade(migration_config, 'head')
    plan=Plan.query.filter_by(code='FREE').first()
    if not plan:
        for code,name in [('FREE','Free'),('PRO','Pro'),('BUSINESS','Business'),('ENTERPRISE','Enterprise'),('CUSTOM','Custom')]:
            db.session.add(Plan(code=code,name=name,limits={'users':10,'storage_mb':1024,'api_requests':10000},features=[]))
        db.session.commit(); plan=Plan.query.filter_by(code='FREE').first()
    org=Organization.query.filter_by(name='UECP Demo Organization').first()
    if not org:
        org=Organization(name='UECP Demo Organization'); db.session.add(org); db.session.flush(); db.session.add(Subscription(organization_id=org.id,plan_id=plan.id,status='ACTIVE'))
    user=User.query.filter_by(email='admin@uecp.local').first()
    if not user:
        user=User(email='admin@uecp.local',password_hash=hash_password(admin_password),is_platform_admin=True); db.session.add(user); db.session.flush(); db.session.add(Membership(user_id=user.id,organization_id=org.id,role='SUPER_ADMIN'))
    db.session.commit()
    print('Seed complete. Platform administrator: admin@uecp.local')

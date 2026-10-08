import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(PROJECT_ROOT / '.env')


def project_path(name, default):
    path = Path(os.getenv(name, str(default))).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path.resolve())

def resolve_database_url():
    raw = os.getenv('DATABASE_URL', '')
    if not raw:
        if os.getenv('VERCEL'):
            return "sqlite:////tmp/uecp.db"
        return f"sqlite:///{(PROJECT_ROOT / 'uecp.db').resolve()}"

    # Auto-encode password and map IPv6-only Supabase direct host to IPv4-ready connection pooler
    if '://' in raw and '@' in raw:
        import urllib.parse
        import re
        scheme, rest = raw.split('://', 1)
        if scheme in ('postgres', 'postgresql', 'postgresql+psycopg'):
            creds, host_part = rest.rsplit('@', 1)
            if ':' in creds:
                u, p = creds.split(':', 1)
                p_encoded = urllib.parse.quote_plus(urllib.parse.unquote(p))
                m = re.match(r'^db\.([a-z0-9]+)\.supabase\.co(?::(\d+))?(.*)$', host_part)
                if m:
                    ref, port, rest_path = m.group(1), m.group(2), m.group(3)
                    if not u.endswith(f'.{ref}'):
                        u = f'{u}.{ref}'
                    host_part = f'aws-0-ap-southeast-2.pooler.supabase.com:5432{rest_path}'
                raw = f"{scheme}://{u}:{p_encoded}@{host_part}"

    if raw.startswith('postgres://'):
        raw = 'postgresql+psycopg://' + raw[len('postgres://'):]
    elif raw.startswith('postgresql://'):
        raw = 'postgresql+psycopg://' + raw[len('postgresql://'):]
    if raw.startswith('postgresql+psycopg://'):
        if 'sslmode=' not in raw:
            sep = '&' if '?' in raw else '?'
            raw = f"{raw}{sep}sslmode=require"

    if raw.startswith('sqlite:///./'):
        rel = raw[len('sqlite:///./'):]
        if os.getenv('VERCEL'):
            return f"sqlite:////tmp/{Path(rel).name}"
        return f"sqlite:///{(PROJECT_ROOT / rel).resolve()}"
    if raw.startswith('sqlite:///') and not raw.startswith('sqlite:////') and ':' not in raw[10:12]:
        sub = raw[len('sqlite:///'):]
        if not Path(sub).is_absolute():
            if os.getenv('VERCEL'):
                return f"sqlite:////tmp/{Path(sub).name}"
            return f"sqlite:///{(PROJECT_ROOT / sub).resolve()}"
    return raw

@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv('ENVIRONMENT', 'development')
    database_url: str = resolve_database_url()
    flask_secret_key: str = os.getenv('FLASK_SECRET_KEY', 'development-only-change-me')
    jwt_private_key_path: str = project_path('JWT_PRIVATE_KEY_PATH', PROJECT_ROOT / 'secrets' / 'jwt_private_key.pem')
    jwt_public_key_path: str = project_path('JWT_PUBLIC_KEY_PATH', PROJECT_ROOT / 'secrets' / 'jwt_public_key.pem')
    jwt_algorithm: str = 'RS256'
    issuer: str = os.getenv('JWT_ISSUER', 'uecp')
    audience: str = os.getenv('JWT_AUDIENCE', 'uecp-api')
    access_token_minutes: int = int(os.getenv('ACCESS_TOKEN_MINUTES', '10'))
    refresh_token_days: int = int(os.getenv('REFRESH_TOKEN_DAYS', '7'))
    cors_origins: str = os.getenv('CORS_ORIGINS', 'http://localhost:5174,http://127.0.0.1:5174')
    rate_limit_storage: str = os.getenv('RATE_LIMIT_STORAGE', 'memory://')
    secure_cookies: bool = os.getenv('SECURE_COOKIES', 'false').lower() == 'true'
    auto_create_tables: bool = os.getenv('AUTO_CREATE_TABLES', 'false').lower() == 'true'
    smtp_host: str = os.getenv('SMTP_HOST', '')
    smtp_port: int = int(os.getenv('SMTP_PORT', '587'))
    smtp_username: str = os.getenv('SMTP_USERNAME', '')
    smtp_password: str = os.getenv('SMTP_PASSWORD', '')
    smtp_from: str = os.getenv('SMTP_FROM', '')

settings = Settings()

if settings.environment == 'production' and os.getenv('STRICT_PRODUCTION_CHECKS', 'false').lower() == 'true':
    if settings.flask_secret_key == 'development-only-change-me':
        raise RuntimeError('FLASK_SECRET_KEY must be configured in production')
    if settings.database_url.startswith('sqlite'):
        raise RuntimeError('SQLite is not permitted in production; use PostgreSQL')
    if settings.rate_limit_storage.startswith('memory://'):
        raise RuntimeError('RATE_LIMIT_STORAGE must use Redis in production')
    if not settings.secure_cookies:
        raise RuntimeError('SECURE_COOKIES must be true in production')
    if not settings.cors_origins.strip() or '*' in settings.cors_origins:
        raise RuntimeError('CORS_ORIGINS must be an explicit production allowlist')

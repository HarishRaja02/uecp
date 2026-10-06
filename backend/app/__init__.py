from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.core.config import settings
from app.db import db

limiter = Limiter(key_func=get_remote_address, default_limits=["300 per minute"], storage_uri=settings.rate_limit_storage)
from app.api.auth import auth_bp
from app.api.admin import admin_bp
from app.api.health import health_bp
from app.api.integration import integration_bp
from app.api.credentials import credentials_bp

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.flask_secret_key,
        SQLALCHEMY_DATABASE_URI=settings.database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    limiter.init_app(app)
    if settings.cors_origins:
        CORS(app, origins=settings.cors_origins.split(','), supports_credentials=True)

    @app.get('/')
    def index():
        return '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>UECP API</title>
  <style>
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f4f6fb; color: #172033; font: 16px/1.5 system-ui, sans-serif; }
    main { width: min(560px, calc(100% - 48px)); padding: 32px; border: 1px solid #e2e7f0; border-radius: 16px; background: white; box-shadow: 0 12px 36px #17203312; }
    h1 { margin: 0 0 8px; font-size: 1.6rem; }
    p { color: #526078; }
    a { color: #3157c8; }
    .status { color: #167447; font-weight: 600; }
    .links { display: flex; flex-wrap: wrap; gap: 18px; margin-top: 24px; }
  </style>
</head>
<body>
  <main>
    <h1>UECP API is running</h1>
    <p class="status">The backend server is available.</p>
    <p>The admin interface runs separately. Start it from the <code>frontend</code> folder with <code>npm run dev</code>.</p>
    <div class="links">
      <a href="http://localhost:5174/">Open the admin interface</a>
      <a href="/api/v1/health">Check API health</a>
    </div>
  </main>
</body>
</html>'''

    @app.get('/favicon.ico')
    def favicon():
        return '', 204

    app.register_blueprint(health_bp, url_prefix='/api/v1')
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/v1/admin')
    app.register_blueprint(integration_bp, url_prefix='/api/v1')
    app.register_blueprint(credentials_bp, url_prefix='/api/v1')

    @app.after_request
    def security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Cache-Control', 'no-store' if request_is_sensitive(response) else 'no-cache')
        if settings.environment == 'production':
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return response

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error='payload_too_large', message='Request payload is too large'), 413

    @app.errorhandler(429)
    def too_many(_):
        return jsonify(error='rate_limited', message='Too many requests'), 429

    with app.app_context():
        if app.config.get('TESTING') and settings.auto_create_tables:
            db.create_all()
    return app

def request_is_sensitive(response):
    return response.headers.get('Content-Type','').startswith('application/json')

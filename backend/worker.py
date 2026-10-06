from app import create_app
from app.core.config import settings
from app.services.expiry import deliver_pending_notifications, process_expirations


app = create_app()

with app.app_context():
    result = process_expirations()
    delivery = {'delivered': 0, 'remaining': 0}
    if settings.smtp_host and settings.smtp_from:
        delivery = deliver_pending_notifications()
    print(f"Expiry pass complete: {result}; notifications: {delivery}")

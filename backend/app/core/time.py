from datetime import timezone


def as_utc(value):
    """Normalize database datetimes before comparing them with UTC timestamps."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

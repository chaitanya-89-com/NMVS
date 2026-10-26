from datetime import datetime, timezone
from app.auth.model import User


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


__all__ = ["User", "utc_now"]

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, field_serializer


INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(INDIA_TIMEZONE)


def now_ist_naive() -> datetime:
    return now_ist().replace(tzinfo=None)


def as_ist(value: datetime) -> datetime:
    # Existing naive database values represent local application time.
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=INDIA_TIMEZONE)
    return value.astimezone(INDIA_TIMEZONE)


class IndiaTimeModel(BaseModel):
    @field_serializer("*", when_used="json")
    def serialize_datetimes_as_ist(self, value):
        if isinstance(value, datetime):
            return as_ist(value).isoformat()
        return value

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from app.timezone import IndiaTimeModel

# pyrefly: ignore[missing-import]
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class SettingsResponse(IndiaTimeModel):
    theme: Literal["light", "dark", "system"]
    email_notifications: bool
    alert_notifications: bool
    timezone: str

    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SettingsUpdate(BaseModel):
    theme: Literal["light", "dark", "system"] | None = None

    email_notifications: bool | None = None
    alert_notifications: bool | None = None

    timezone: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value):
        if value is not None:
            value = value.strip()

            if not value:
                raise ValueError("Timezone cannot be empty")

            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError("Timezone must be a valid IANA timezone") from exc

        return value


class ProfileResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    email_verified: bool

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
    )

    email: EmailStr | None = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value):
        if value is not None:
            value = value.strip()

            if not value:
                raise ValueError("Username cannot be empty")

        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if value is not None:
            return str(value).strip().lower()

        return value
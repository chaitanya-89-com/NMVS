import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.timezone import IndiaTimeModel

def _validate_strong_password(v: str) -> str:
    if len(v) < 12:
        raise ValueError("Password must be at least 12 characters long")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"[0-9]", v):
        raise ValueError("Password must contain at least one number")
    if not re.search(r"[^A-Za-z0-9\s]", v):
        raise ValueError("Password must contain at least one symbol")
    return v


class RegisterUser(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_strong_password(v)

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm_password(cls, v: str) -> str:
        return _validate_strong_password(v)

    @model_validator(mode="after")
    def validate_password_confirmation(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    otp: str | None = None


class VerifyResetOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        if not re.fullmatch(r"[0-9]{6}", v):
            raise ValueError("OTP must contain exactly six digits")
        return v


class ResetPasswordRequest(BaseModel):
    token: str | None = None
    password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_strong_password(v)

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm_password(cls, v: str) -> str:
        return _validate_strong_password(v)

    @model_validator(mode="after")
    def validate_password_confirmation(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_strong_password(v)

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm_password(cls, v: str) -> str:
        return _validate_strong_password(v)

    @model_validator(mode="after")
    def validate_password_confirmation(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UserResponse(IndiaTimeModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    email_verified: bool | None = False

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    message: str
    user: UserResponse


class ResetTokenResponse(BaseModel):
    reset_token: str
    token_type: str
    message: str


class MessageResponse(BaseModel):
    message: str
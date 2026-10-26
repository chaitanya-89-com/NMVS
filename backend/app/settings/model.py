# pyrefly: ignore[missing-import]
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
# pyrefly: ignore[missing-import]
from sqlalchemy.orm import relationship

from app.timezone import now_ist
from database.database import Base


class UserSettings(Base):
    """Store preferences for each user."""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    theme = Column(
        String(10),
        nullable=False,
        default="light",
        server_default="light",
    )

    email_notifications = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    alert_notifications = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    timezone = Column(
        String(64),
        nullable=False,
        default="Asia/Kolkata",
        server_default="Asia/Kolkata",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=now_ist,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=now_ist,
        server_default=func.now(),
        onupdate=now_ist,
    )

    user = relationship(
        "User",
        backref="settings",
        uselist=False,
    )
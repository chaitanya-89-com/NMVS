# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.settings.model import UserSettings
from app.users.model import User


def get_or_create_settings(
    db: Session,
    user_id: int,
) -> UserSettings:

    settings = (
        db.query(UserSettings)
        .filter(UserSettings.user_id == user_id)
        .first()
    )

    if settings is not None:
        return settings

    settings = UserSettings(user_id=user_id)

    db.add(settings)
    db.commit()
    db.refresh(settings)

    return settings


def update_settings(
    db: Session,
    user_id: int,
    changes: dict,
) -> UserSettings:

    settings = get_or_create_settings(db, user_id)

    for field, value in changes.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)

    return settings


def update_profile(
    db: Session,
    user: User,
    changes: dict,
) -> User:

    if "username" in changes:
        username = changes["username"]

        existing = (
            db.query(User.id)
            .filter(
                User.username == username,
                User.id != user.id,
            )
            .first()
        )

        if existing:
            raise ValueError("Username already exists")

        user.username = username

    if "email" in changes:
        new_email = str(changes["email"]).strip().lower()

        existing = (
            db.query(User.id)
            .filter(
                User.email == new_email,
                User.id != user.id,
            )
            .first()
        )

        if existing:
            raise ValueError("Email already registered")

        if new_email != user.email.lower():
            user.email = new_email

            # Require email verification again.
            user.email_verified = False

    db.commit()
    db.refresh(user)

    return user
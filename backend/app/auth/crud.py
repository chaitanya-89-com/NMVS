from datetime import datetime, timezone
import hmac

# pyrefly: ignore[missing-import]
from sqlalchemy.exc import IntegrityError

from database.database import SessionLocal
from app.auth.model import User
from app.auth.security import hash_reset_otp, hash_reset_token


def get_user_by_username(username: str):
    db = SessionLocal()

    try:
        return (
            db.query(User)
            .filter(User.username == username.strip())
            .first()
        )
    finally:
        db.close()


def get_user_by_email(email: str):
    db = SessionLocal()

    try:
        return (
            db.query(User)
            .filter(User.email == email.strip().lower())
            .first()
        )
    finally:
        db.close()


def get_user_by_id(user_id: int):
    db = SessionLocal()

    try:
        return (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )
    finally:
        db.close()


def create_user(
    username: str,
    email: str,
    hashed_password: str
):
    db = SessionLocal()

    try:
        user = User(
            username=username.strip(),
            email=email.strip().lower(),
            hashed_password=hashed_password,
            is_active=True,
            email_verified=False,
            email_otp=None,
            otp_expires_at=None
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    except IntegrityError:
        db.rollback()
        raise ValueError(
            "Username or email already exists"
        )

    except Exception as e:
        db.rollback()
        print(f"DATABASE CREATE USER ERROR: {type(e).__name__}: {e}")
        raise

    finally:
        db.close()


def get_all_users():
    db = SessionLocal()
    try:
        return (
            db.query(User)
            .order_by(User.id.desc())
            .all()
        )
    finally:
        db.close()


def save_reset_otp(
    user_id: int,
    otp: str,
    expires_at: datetime
):
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        if user is None:
            return None

        user.email_otp = f"v1:0:{hash_reset_otp(user_id, otp)}"
        user.otp_expires_at = expires_at
        user.password_reset_token_hash = None
        user.password_reset_token_expires_at = None

        db.commit()
        db.refresh(user)

        return user

    finally:
        db.close()


def verify_reset_otp(
    email: str,
    otp: str
):
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.email == email.strip().lower())
            .first()
        )

        if user is None:
            return None

        if user.otp_expires_at is None:
            return None

        expires_at = user.otp_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        if now >= expires_at:
            user.email_otp = None
            user.otp_expires_at = None
            db.commit()
            return None

        stored_otp = user.email_otp or ""
        attempts = 0
        if stored_otp.startswith("v1:"):
            try:
                version, attempts_text, expected_hash = stored_otp.split(":", 2)
                attempts = int(attempts_text)
                if version != "v1" or not 0 <= attempts < 5:
                    return None
                otp_matches = hmac.compare_digest(
                    expected_hash,
                    hash_reset_otp(user.id, otp),
                )
            except (ValueError, TypeError):
                return None
        else:
            expected_hash = hash_reset_otp(user.id, stored_otp)
            otp_matches = hmac.compare_digest(stored_otp, otp)

        if not otp_matches:
            attempts += 1
            if attempts >= 5:
                user.email_otp = None
                user.otp_expires_at = None
            else:
                user.email_otp = f"v1:{attempts}:{expected_hash}"
            db.commit()
            return None

        # OTP can only be used once.
        user.email_otp = None
        user.otp_expires_at = None

        db.commit()
        db.refresh(user)

        return user

    finally:
        db.close()


def update_password(
    user_id: int,
    hashed_password: str
):
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        if user is None:
            return None

        user.hashed_password = hashed_password
        user.email_otp = None
        user.otp_expires_at = None
        user.password_reset_token_hash = None
        user.password_reset_token_expires_at = None

        db.commit()
        db.refresh(user)

        return user

    finally:
        db.close()


def save_password_reset_token(
    user_id: int,
    token: str,
    expires_at: datetime,
):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return None

        user.email_otp = None
        user.otp_expires_at = None
        user.password_reset_token_hash = hash_reset_token(token)
        user.password_reset_token_expires_at = expires_at
        db.commit()
        return user
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_password_with_reset_token(
    user_id: int,
    hashed_password: str,
    token: str,
):
    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )
        if user is None or not user.password_reset_token_hash:
            return None

        expires_at = user.password_reset_token_expires_at
        if expires_at is None:
            return None
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expires_at:
            user.password_reset_token_hash = None
            user.password_reset_token_expires_at = None
            db.commit()
            return None

        supplied_hash = hash_reset_token(token)
        if not hmac.compare_digest(user.password_reset_token_hash, supplied_hash):
            return None

        user.hashed_password = hashed_password
        user.password_reset_token_hash = None
        user.password_reset_token_expires_at = None
        user.email_otp = None
        user.otp_expires_at = None
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def clear_reset_otp(user_id: int):
    """Invalidate a reset OTP when email delivery fails."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is not None:
            user.email_otp = None
            user.otp_expires_at = None
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

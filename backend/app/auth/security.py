import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

from app.config import settings


def validate_password_strength(password: str) -> tuple[bool, str | None]:
    """
    Validate that password meets strong security standards:
    - Minimum 12 characters
    - At least one uppercase and one lowercase letter
    - At least one numeric digit
    - At least one non-alphanumeric symbol
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[^A-Za-z0-9\s]", password):
        return False, "Password must contain at least one symbol"
    return True, None


# -------------------------------------------------------------
# Optional 3rd party libraries with zero-dependency fallbacks
# -------------------------------------------------------------
try:
    import bcrypt
except ImportError:
    bcrypt = None

try:
    from jose import jwt as jose_jwt
except ImportError:
    jose_jwt = None

try:
    import jwt as py_jwt
except ImportError:
    py_jwt = None


# -------------------------------------------------------------
# Password Hashing & Verification (Bcrypt + PBKDF2 fallback)
# -------------------------------------------------------------
def _hash_pbkdf2(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 600_000
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${derived}"


def _verify_pbkdf2(password: str, hashed_password: str) -> bool:
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_hash = parts[3]
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations
        ).hex()
        return hmac.compare_digest(derived, expected_hash)
    except Exception:
        return False


def hash_password(password: str) -> str:
    if bcrypt is not None:
        try:
            pwd_bytes = hashlib.sha256(
                b"nmvs-bcrypt-sha256-v1\0" + password.encode("utf-8")
            ).digest()
            salt = bcrypt.gensalt(rounds=12)
            hashed = bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")
            return f"bcrypt_sha256${hashed}"
        except Exception:
            pass
    return _hash_pbkdf2(password)


def verify_password(password: str, hashed_password: str) -> bool:
    if not password or not hashed_password:
        return False

    if hashed_password.startswith("bcrypt_sha256$"):
        if bcrypt is None:
            return False
        try:
            pwd_bytes = hashlib.sha256(
                b"nmvs-bcrypt-sha256-v1\0" + password.encode("utf-8")
            ).digest()
            stored_hash = hashed_password.split("$", 1)[1].encode("utf-8")
            return bcrypt.checkpw(pwd_bytes, stored_hash)
        except Exception:
            return False

    # Check for bcrypt format ($2b$, $2a$, $2y$)
    if hashed_password.startswith(("$2b$", "$2a$", "$2y$")):
        if bcrypt is not None:
            try:
                pwd_bytes = password.encode("utf-8")[:72]
                return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
            except Exception:
                return False
        return False

    # Check for PBKDF2 format
    if hashed_password.startswith("pbkdf2_sha256$"):
        return _verify_pbkdf2(password, hashed_password)

    return False


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_reset_otp(user_id: int, otp: str) -> str:
    message = f"password-reset:{user_id}:{otp}".encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def hash_reset_token(token: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        b"password-reset-token:" + token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# -------------------------------------------------------------
# JWT Encoding & Decoding (jose / pyjwt / standard library)
# -------------------------------------------------------------
def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(s: str) -> bytes:
    padding = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode((s + padding).encode("utf-8"))


def _encode_jwt(payload: dict, secret: str, algorithm: str = "HS256") -> str:
    if jose_jwt is not None:
        try:
            return jose_jwt.encode(payload, secret, algorithm=algorithm)
        except Exception:
            pass

    if py_jwt is not None:
        try:
            return py_jwt.encode(payload, secret, algorithm=algorithm)
        except Exception:
            pass

    # Built-in Standard Library JWT Encoder
    header = {"typ": "JWT", "alg": "HS256"}
    h_b64 = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _base64url_encode(sig)
    return f"{h_b64}.{p_b64}.{sig_b64}"


def _decode_jwt(token: str, secret: str, algorithm: str = "HS256") -> dict | None:
    if jose_jwt is not None:
        try:
            return jose_jwt.decode(
                token,
                secret,
                algorithms=[algorithm],
                options={"require_exp": True},
            )
        except Exception:
            return None

    if py_jwt is not None:
        try:
            return py_jwt.decode(
                token,
                secret,
                algorithms=[algorithm],
                options={"require": ["exp"]},
            )
        except Exception:
            return None

    # Built-in Standard Library JWT Decoder
    try:
        if algorithm != "HS256":
            return None
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        h_b64, p_b64, sig_b64 = parts
        header = json.loads(_base64url_decode(h_b64).decode("utf-8"))
        if header.get("alg") != algorithm:
            return None
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _base64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_base64url_decode(p_b64).decode("utf-8"))
        exp = payload.get("exp")
        if exp is None or int(exp) <= int(time.time()):
            return None
        return payload
    except Exception:
        return None


def create_access_token(user_id: int) -> str:
    expire_minutes = int(getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60))
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": str(user_id),
        "purpose": "access",
        "exp": int(expire.timestamp())
    }
    return _encode_jwt(
        payload,
        settings.SECRET_KEY,
        settings.ALGORITHM
    )


def create_reset_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {
        "sub": str(user_id),
        "purpose": "password_reset",
        "exp": int(expire.timestamp())
    }
    return _encode_jwt(
        payload,
        settings.SECRET_KEY,
        settings.ALGORITHM
    )


def decode_access_token(token: str) -> int | None:
    payload = _decode_jwt(
        token,
        settings.SECRET_KEY,
        settings.ALGORITHM
    )
    if not payload or payload.get("purpose") != "access":
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return None


def decode_reset_token(token: str) -> int | None:
    payload = _decode_jwt(
        token,
        settings.SECRET_KEY,
        settings.ALGORITHM
    )
    if not payload or payload.get("purpose") != "password_reset":
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return None

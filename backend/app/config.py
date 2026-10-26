"""Application settings loaded from environment variables or a local .env file.

No real credentials are shipped with the project. In development, an ephemeral
JWT key is generated when NMVS_SECRET_KEY is absent; it changes on each process
start. Production must set a stable, high-entropy NMVS_SECRET_KEY explicitly.
"""

import os
import secrets
import warnings

from dotenv import load_dotenv

# Do not override variables supplied by the process/container environment.
load_dotenv(override=False)


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}")
    return value


def _float_env(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}")
    return value


class Settings:
    PROJECT_NAME = "Network Monitoring and Visualization System"
    DEVICE_MONITOR_INTERVAL = _int_env("DEVICE_MONITOR_INTERVAL", 30)
    MONITORING_UNREACHABLE_CONSECUTIVE_CHECKS = _int_env(
        "MONITORING_UNREACHABLE_CONSECUTIVE_CHECKS", 3
    )
    MONITORING_HIGH_LATENCY_MS = _float_env("MONITORING_HIGH_LATENCY_MS", 500.0)
    MONITORING_UPTIME_THRESHOLD_PERCENT = _float_env(
        "MONITORING_UPTIME_THRESHOLD_PERCENT", 95.0
    )
    if MONITORING_UPTIME_THRESHOLD_PERCENT > 100:
        raise RuntimeError("MONITORING_UPTIME_THRESHOLD_PERCENT must be <= 100")
    MONITORING_HTTP_TIMEOUT_SECONDS = _float_env(
        "MONITORING_HTTP_TIMEOUT_SECONDS", 5.0, minimum=0.1
    )
    MONITORING_HTTP_ALLOWED_HOSTS = frozenset(
        host.strip().lower().rstrip(".")
        for host in os.getenv("MONITORING_HTTP_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    )
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = _int_env("ACCESS_TOKEN_EXPIRE_MINUTES", 15)

    ENVIRONMENT = os.getenv("NMVS_ENVIRONMENT", "development").strip().lower()
    _configured_secret = os.getenv("NMVS_SECRET_KEY", "").strip()

    if ENVIRONMENT == "production":
        if len(_configured_secret) < 32 or _configured_secret.lower().startswith(("change", "replace", "your_")):
            raise RuntimeError(
                "Set NMVS_SECRET_KEY to a unique random secret of at least 32 characters in production."
            )
        SECRET_KEY = _configured_secret
    else:
        SECRET_KEY = _configured_secret or secrets.token_urlsafe(48)
        if not _configured_secret:
            warnings.warn(
                "NMVS_SECRET_KEY is not set; using an ephemeral development key. "
                "Sessions will become invalid after restart. Set NMVS_SECRET_KEY for stable local sessions.",
                RuntimeWarning,
                stacklevel=2,
            )

    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    SMTP_PORT = _int_env("SMTP_PORT", 587)

    @property
    def SMTP_USERNAME(self) -> str:
        return os.getenv("SMTP_USERNAME", "").strip()

    @property
    def SMTP_PASSWORD(self) -> str:
        # Gmail app passwords are often displayed with spaces; normalize them.
        return os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()

    @property
    def SMTP_FROM_EMAIL(self) -> str:
        return os.getenv("SMTP_FROM_EMAIL", "").strip()


settings = Settings()

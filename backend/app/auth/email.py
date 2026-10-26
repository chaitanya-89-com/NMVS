import smtplib
import ssl
from email.message import EmailMessage

from app.config import settings


def send_otp_email(
    email: str,
    otp: str
):

    message = EmailMessage()

    message["Subject"] = "NMVS Password Reset OTP"
    message["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
    message["To"] = email

    message.set_content(
        f"""
Hello,

Your NMVS password reset OTP is:

{otp}

This OTP will expire in 10 minutes.

If you did not request a password reset,
please ignore this email.

Regards,
NMVS
"""
    )

    smtp_user = str(settings.SMTP_USERNAME).strip()
    smtp_pass = str(settings.SMTP_PASSWORD).replace(" ", "").strip()

    if not smtp_pass or not smtp_user:
        raise RuntimeError("SMTP credentials are not configured in .env (SMTP_USERNAME / SMTP_PASSWORD)")

    context = ssl.create_default_context()
    port = int(settings.SMTP_PORT)

    if port == 465:
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            port,
            context=context,
            timeout=15
        ) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(message)
    else:
        with smtplib.SMTP(
            settings.SMTP_HOST,
            port,
            timeout=15
        ) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(message)
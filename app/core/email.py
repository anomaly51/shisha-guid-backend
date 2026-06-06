import smtplib
import atexit
from threading import Lock
from email.message import EmailMessage

from app.core.config import settings


_smtp_client: smtplib.SMTP | None = None
_smtp_lock = Lock()


def _create_smtp_client() -> smtplib.SMTP:
    client = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
    if settings.SMTP_USE_TLS:
        client.starttls()
    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
        client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
    return client


def _get_smtp_client() -> smtplib.SMTP:
    global _smtp_client
    with _smtp_lock:
        if _smtp_client is not None:
            try:
                _smtp_client.noop()
                return _smtp_client
            except Exception:
                try:
                    _smtp_client.quit()
                except Exception:
                    pass
                _smtp_client = None

        _smtp_client = _create_smtp_client()
        return _smtp_client


def _close_smtp_client() -> None:
    global _smtp_client
    with _smtp_lock:
        if _smtp_client is None:
            return
        try:
            _smtp_client.quit()
        except Exception:
            try:
                _smtp_client.close()
            except Exception:
                pass
        finally:
            _smtp_client = None


atexit.register(_close_smtp_client)


def send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        return

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    client = _get_smtp_client()
    with _smtp_lock:
        client.send_message(message)

from fastapi import Cookie, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pwdlib import PasswordHash

from app.config import get_settings
from app.runtime import use_dev_auth

password_hash = PasswordHash.recommended()


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt="admin-session")


def create_session(user_id: str, email: str) -> str:
    return _serializer().dumps({"sub": user_id, "email": email})


def require_admin(session: str | None = Cookie(default=None)) -> dict[str, str]:
    settings = get_settings()
    if use_dev_auth(settings):
        return {"sub": str(settings.dev_admin_id), "email": settings.dev_admin_email}
    if session is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = _serializer().loads(session, max_age=60 * 60 * 12)
        return {"sub": str(payload["sub"]), "email": str(payload["email"])}
    except (BadSignature, SignatureExpired, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc

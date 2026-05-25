from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from supabase import Client, ClientOptions, create_client
from supabase_auth.errors import AuthError

from app.config import get_settings
from app.db import get_db
from app.models import AdminUser
from app.runtime import use_dev_auth
from app.schemas import AdminResponse, LoginRequest
from app.security import create_session, require_admin

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
SUPABASE_AUTH_PROFILE_MARKER = "supabase-auth"


def create_supabase_auth_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise RuntimeError("Supabase authentication credentials are not configured")
    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def _field(source: object, name: str) -> object | None:
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def _app_metadata(user: object) -> dict[str, object]:
    metadata = _field(user, "app_metadata") or _field(user, "raw_app_meta_data") or {}
    return metadata if isinstance(metadata, dict) else {}


def _has_admin_role(user: object) -> bool:
    metadata = _app_metadata(user)
    if metadata.get("role") == "admin":
        return True
    roles = metadata.get("roles")
    return isinstance(roles, list) and "admin" in roles


def authenticate_admin(
    email: str, password: str, db: Session
) -> dict[str, str]:
    settings = get_settings()
    if use_dev_auth(settings):
        return {"sub": str(settings.dev_admin_id), "email": settings.dev_admin_email}

    normalized_email = email.strip().lower()
    try:
        auth_response = create_supabase_auth_client().auth.sign_in_with_password(
            {"email": normalized_email, "password": password}
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail="Invalid credentials") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    user = _field(auth_response, "user")
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not _has_admin_role(user):
        raise HTTPException(status_code=403, detail="Administrator access is required")

    user_id = UUID(str(_field(user, "id")))
    user_email = str(_field(user, "email") or normalized_email).lower()
    profile = db.get(AdminUser, user_id) or db.scalar(
        select(AdminUser).where(AdminUser.email == user_email)
    )
    if profile is None:
        db.add(
            AdminUser(
                id=user_id,
                email=user_email,
                password_hash=SUPABASE_AUTH_PROFILE_MARKER,
            )
        )
    elif profile.email != user_email:
        profile.email = user_email
    if profile is not None:
        profile.password_hash = SUPABASE_AUTH_PROFILE_MARKER
    db.commit()
    return {"sub": str(profile.id if profile else user_id), "email": user_email}


@router.post("/login", response_model=AdminResponse)
def login(
    payload: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> AdminResponse:
    admin = authenticate_admin(payload.email, payload.password, db)
    response.set_cookie(
        "session",
        create_session(admin["sub"], admin["email"]),
        httponly=True,
        secure=get_settings().session_cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return AdminResponse(email=admin["email"])


@router.get("/me", response_model=AdminResponse)
def me(admin: dict[str, str] = Depends(require_admin)) -> AdminResponse:
    return AdminResponse(email=admin["email"])


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(
        "session",
        httponly=True,
        secure=get_settings().session_cookie_secure,
        samesite="lax",
    )

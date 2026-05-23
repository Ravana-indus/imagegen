from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import AdminUser
from app.schemas import AdminResponse, LoginRequest
from app.security import create_session, password_hash, require_admin

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=AdminResponse)
def login(
    payload: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> AdminResponse:
    user = db.scalar(select(AdminUser).where(AdminUser.email == payload.email.lower()))
    if user is None or not password_hash.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response.set_cookie(
        "session",
        create_session(str(user.id), user.email),
        httponly=True,
        secure=get_settings().session_cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return AdminResponse(email=user.email)


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

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.security import create_session, require_admin


def test_signed_session_round_trips_admin_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.security.get_settings",
        lambda: SimpleNamespace(session_secret="long-development-secret"),
    )
    session = create_session("admin-id", "owner@example.com")

    assert require_admin(session) == {
        "sub": "admin-id",
        "email": "owner@example.com",
    }


def test_missing_session_is_unauthorized(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.security.get_settings",
        lambda: SimpleNamespace(session_secret="long-development-secret", auth_mode="session"),
    )
    with pytest.raises(HTTPException) as error:
        require_admin(None)

    assert error.value.status_code == 401

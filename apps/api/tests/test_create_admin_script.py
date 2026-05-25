from types import SimpleNamespace
from uuid import uuid4

from scripts.create_admin import ensure_supabase_admin


class FakeAdminApi:
    def __init__(
        self, users: list[object] | None = None, *, return_list: bool = False
    ) -> None:
        self.users = users or []
        self.return_list = return_list
        self.created: dict[str, object] | None = None
        self.updated: tuple[str, dict[str, object]] | None = None

    def list_users(self, page: int, per_page: int):
        if self.return_list:
            return self.users
        return SimpleNamespace(users=self.users)

    def create_user(self, attributes: dict[str, object]):
        self.created = attributes
        user = SimpleNamespace(id=str(uuid4()), email=attributes["email"])
        return SimpleNamespace(user=user)

    def update_user_by_id(self, user_id: str, attributes: dict[str, object]):
        self.updated = (user_id, attributes)
        user = SimpleNamespace(
            id=user_id, email=attributes.get("email", "owner@example.com")
        )
        return SimpleNamespace(user=user)


class FakeClient:
    def __init__(self, admin: FakeAdminApi) -> None:
        self.auth = SimpleNamespace(admin=admin)


def test_ensure_supabase_admin_creates_confirmed_admin_user() -> None:
    admin = FakeAdminApi()

    user = ensure_supabase_admin(
        FakeClient(admin), "Owner@Example.com", "correct-password"
    )

    assert admin.created == {
        "email": "owner@example.com",
        "password": "correct-password",
        "email_confirm": True,
        "app_metadata": {"role": "admin"},
    }
    assert user.email == "owner@example.com"


def test_ensure_supabase_admin_updates_existing_user_password_and_role() -> None:
    user_id = str(uuid4())
    existing = SimpleNamespace(id=user_id, email="owner@example.com")
    admin = FakeAdminApi([existing], return_list=True)

    user = ensure_supabase_admin(
        FakeClient(admin), "Owner@Example.com", "new-password"
    )

    assert admin.created is None
    assert admin.updated == (
        user_id,
        {
            "email": "owner@example.com",
            "password": "new-password",
            "email_confirm": True,
            "app_metadata": {"role": "admin"},
        },
    )
    assert user.id == user_id

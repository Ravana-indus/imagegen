import argparse
from getpass import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supabase import Client, ClientOptions, create_client

from app.config import get_settings


def create_supabase_admin_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SECRET_KEY must be configured.")
    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def field(source: object, name: str) -> object | None:
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def find_user_by_email(client: Client, email: str) -> object | None:
    response = client.auth.admin.list_users(page=1, per_page=1000)
    users = response if isinstance(response, list) else field(response, "users") or []
    for user in users:
        if str(field(user, "email") or "").lower() == email:
            return user
    return None


def ensure_supabase_admin(client: Client, email: str, password: str) -> object:
    normalized_email = email.strip().lower()
    attributes: dict[str, object] = {
        "email": normalized_email,
        "password": password,
        "email_confirm": True,
        "app_metadata": {"role": "admin"},
    }
    existing_user = find_user_by_email(client, normalized_email)
    if existing_user is not None:
        response = client.auth.admin.update_user_by_id(
            str(field(existing_user, "id")), attributes
        )
    else:
        response = client.auth.admin.create_user(attributes)
    user = field(response, "user")
    if user is None:
        raise SystemExit("Supabase Auth did not return a user.")
    return user


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or update a Supabase Auth administrator."
    )
    parser.add_argument("email", help="Administrator email address")
    args = parser.parse_args()
    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if len(password) < 6:
        raise SystemExit("Password must contain at least 6 characters.")

    user = ensure_supabase_admin(create_supabase_admin_client(), args.email, password)
    print(f"Ensured Supabase administrator {field(user, 'email')}.")


if __name__ == "__main__":
    main()

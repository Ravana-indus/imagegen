import argparse
from getpass import getpass

from sqlalchemy import select

from app.db import get_db
from app.models import AdminUser
from app.security import password_hash


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the application administrator.")
    parser.add_argument("email", help="Administrator email address")
    args = parser.parse_args()
    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")

    db = next(get_db())
    try:
        email = args.email.strip().lower()
        if db.scalar(select(AdminUser).where(AdminUser.email == email)):
            raise SystemExit("Administrator already exists.")
        db.add(AdminUser(email=email, password_hash=password_hash.hash(password)))
        db.commit()
        print(f"Created administrator {email}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

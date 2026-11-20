import getpass
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.core.security import hash_password
from app.models import AdminUser, Role


ROLE_NAME = "SUPER_ADMIN"
MIN_PASSWORD_LENGTH = 12


def main():
    print("=== First Administrator Setup ===")
    print("This command creates the initial administrator account.")
    print("It can only be used while no administrator accounts exist.\n")

    name = input("Administrator name: ").strip()
    email = input("Administrator email: ").strip().lower()

    if not name:
        print("Error: Name cannot be empty.")
        return 1

    if not email or "@" not in email or email.startswith("@"):
        print("Error: Enter a valid email address.")
        return 1

    password = getpass.getpass("Password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")

    if len(password) < MIN_PASSWORD_LENGTH:
        print("Error: Password must contain at least 12 characters.")
        return 1

    if password != confirmation:
        print("Error: Passwords do not match.")
        return 1

    try:
        with Session(engine) as db:
            with db.begin():
                existing_admin = db.scalar(
                    select(AdminUser.id).limit(1)
                )

                if existing_admin is not None:
                    print(
                        "Error: An administrator already exists. "
                        "Bootstrap refused."
                    )
                    return 1

                role = db.scalar(
                    select(Role).where(Role.name == ROLE_NAME)
                )

                if role is None:
                    role = Role(
                        name=ROLE_NAME,
                        description="Full administrative access",
                    )
                    db.add(role)
                    db.flush()

                admin = AdminUser(
                    name=name,
                    email=email,
                    password_hash=hash_password(password),
                    role_id=role.id,
                    is_active=True,
                )

                db.add(admin)
                db.flush()

                admin_id = admin.id

        print("\nFirst administrator created successfully.")
        print(f"Administrator ID: {admin_id}")
        print(f"Role: {ROLE_NAME}")
        print("You can now use the admin login endpoint.")

        return 0

    except IntegrityError:
        print(
            "Error: Database constraint violation. "
            "The transaction was rolled back."
        )
        return 1

    except Exception as exc:
        print(f"Error: Administrator creation failed ({type(exc).__name__}).")
        return 1

    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())

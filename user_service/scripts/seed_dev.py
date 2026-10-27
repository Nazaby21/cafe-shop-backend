#!/usr/bin/env python
"""
Seed script for local development.

Refuses to run when ENVIRONMENT=production.
Seeds test-marked users:
  - test_admin@example.com (admin)
  - test_staff@example.com (staff)
  - test_customer@example.com (customer)

Marker convention:
  - Email prefix: test_
  - Email domain: example.com
  - Username prefix: test_
"""
import argparse
import sys
from pathlib import Path

# Add user_service root to sys.path so app imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User


DEV_USERS = [
    {
        "username": "test_admin",
        "email": "test_admin@example.com",
        "password": "Password123!",
        "role": "admin",
    },
    {
        "username": "test_staff",
        "email": "test_staff@example.com",
        "password": "Password123!",
        "role": "staff",
    },
    {
        "username": "test_customer",
        "email": "test_customer@example.com",
        "password": "Password123!",
        "role": "customer",
    },
]


def seed(dry_run: bool = True) -> int:
    if settings.is_production:
        print("ERROR: Cannot run seed script in production environment!", file=sys.stderr)
        return 1

    print(f"Target database: {settings.DB_NAME or settings.database_url}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Mode: {'DRY-RUN (no changes will be committed)' if dry_run else 'EXECUTE'}")

    db = SessionLocal()
    try:
        to_create = []
        for u in DEV_USERS:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if existing:
                print(f"  [EXISTS] User {u['email']} (id={existing.id}, role={existing.role})")
            else:
                to_create.append(u)
                print(f"  [TO CREATE] User {u['email']} (role={u['role']})")

        if not to_create:
            print("Nothing to seed. All dev users already exist.")
            return 0

        if dry_run:
            print(f"\nDry-run complete: {len(to_create)} user(s) would be created.")
            return 0

        for u in to_create:
            user = User(
                username=u["username"],
                email=u["email"],
                password=hash_password(u["password"]),
                role=u["role"],
                is_active=True,
            )
            db.add(user)

        db.commit()
        print(f"\nSuccessfully seeded {len(to_create)} user(s).")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"ERROR: Seeding failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed development users in user_service")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute changes (default is dry-run mode)",
    )
    args = parser.parse_args()
    sys.exit(seed(dry_run=not args.execute))


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""
Clean up test users from user_service database.

Follows the cascade and isolation rules:
- Deletes only rows matched by the test marker or explicitly specified by ID.
- Exports matched rows to a JSON backup before performing hard delete.
- Default mode is DRY-RUN. Use --execute to apply changes.
- Wrapped in a database transaction with rollback on any error.

Marker convention:
- Email matches *@example.test, *@example.com, test@*, etc.
- Or user ID in --ids list.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add user_service root to sys.path so app imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User


def get_suspected_test_users(db, specific_ids: list[int] | None = None):
    query = db.query(User)
    if specific_ids:
        return query.filter(User.id.in_(specific_ids)).all()

    # Look for RFC test domain, test usernames, or common test patterns
    all_users = query.all()
    matched = []
    test_domains = ("example.test", "example.com", "example.org", "example.net", "test.local", "mailinator.com")
    test_prefixes = ("test_", "test-", "demo_", "dummy_", "fake_")

    for user in all_users:
        email = (user.email or "").lower()
        username = (user.username or "").lower()
        domain = email.split("@")[-1] if "@" in email else ""

        is_test_email = domain in test_domains or domain.endswith(".test") or email.startswith("test@")
        is_test_username = any(username.startswith(prefix) for prefix in test_prefixes) or username in ("alice", "bob", "john")

        if is_test_email or is_test_username:
            matched.append(user)

    return matched


def run_cleanup(execute: bool = False, specific_ids: list[int] | None = None, backup_dir: Path | None = None) -> int:
    backup_dir = backup_dir or (Path(__file__).resolve().parent.parent / "backups")
    print(f"Target database: {settings.DB_NAME or settings.database_url}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Mode: {'EXECUTE (will backup and delete)' if execute else 'DRY-RUN (read-only preview)'}")

    db = SessionLocal()
    try:
        users_to_delete = get_suspected_test_users(db, specific_ids)
        total_count = len(users_to_delete)

        print(f"\nFound {total_count} matching test user(s):")
        for u in users_to_delete:
            print(f"  [ID {u.id}] username={u.username!r}, email={u.email!r}, role={u.role}, active={u.is_active}, created={u.created_at}")

        if total_count == 0:
            print("\nNo test users found. Nothing to clean up.")
            return 0

        if not execute:
            print("\n[DRY-RUN] No changes were made to the database.")
            print("Run with --execute to perform backup and hard-deletion.")
            return 0

        # Step 1: Backup to JSON
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"users_backup_{timestamp}.json"

        backup_payload = [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "password_hash": u.password,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
                "deleted_at": u.deleted_at.isoformat() if u.deleted_at else None,
            }
            for u in users_to_delete
        ]

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_payload, f, indent=2)
        print(f"\n[BACKUP] Successfully exported {total_count} record(s) to: {backup_file}")

        # Step 2: Hard delete
        deleted_ids = [u.id for u in users_to_delete]
        db.query(User).filter(User.id.in_(deleted_ids)).delete(synchronize_session=False)
        db.commit()

        print(f"[DELETED] Successfully hard-deleted {total_count} user(s) from user_service.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"ERROR: Cleanup failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Cleanup test users from user_service")
    parser.add_argument("--execute", action="store_true", help="Execute deletion (default: dry-run)")
    parser.add_argument("--ids", type=str, help="Comma-separated list of specific user IDs to delete")
    parser.add_argument("--backup-dir", type=Path, help="Directory to save backup JSON file")
    args = parser.parse_args()

    specific_ids = [int(i.strip()) for i in args.ids.split(",") if i.strip()] if args.ids else None
    sys.exit(run_cleanup(execute=args.execute, specific_ids=specific_ids, backup_dir=args.backup_dir))


if __name__ == "__main__":
    main()

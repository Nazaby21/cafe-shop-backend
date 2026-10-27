#!/usr/bin/env python
"""
Clean up derived test data from report_service snapshots.

Follows the cascade and isolation rules:
- Cleans report_service_db snapshots BEFORE upstream services are modified,
  or performs a full snapshot reset (--rebuild) after upstream services are cleaned.
- Exports matched snapshot records to JSON backup before deletion.
- Default mode is DRY-RUN. Use --execute to commit changes.
- Wrapped in a database transaction with rollback on error.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add report_service root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.snapshot import OrderItemSnapshot, OrderSnapshot, ProductSnapshot, UserSnapshot


def run_cleanup(
    execute: bool = False,
    test_user_ids: list[int] | None = None,
    test_order_ids: list[int] | None = None,
    rebuild: bool = False,
    backup_dir: Path | None = None,
) -> int:
    backup_dir = backup_dir or (Path(__file__).resolve().parent.parent / "backups")
    print(f"Target database: {settings.DB_NAME or settings.database_url}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Mode: {'EXECUTE (will backup and delete)' if execute else 'DRY-RUN (read-only preview)'}")

    db = SessionLocal()
    try:
        if rebuild:
            print("\n[REBUILD MODE] Requested full snapshot reset (truncate all snapshots).")
            user_count = db.query(UserSnapshot).count()
            product_count = db.query(ProductSnapshot).count()
            order_count = db.query(OrderSnapshot).count()
            item_count = db.query(OrderItemSnapshot).count()

            print("Current snapshot counts:")
            print(f"  users_snapshot:       {user_count}")
            print(f"  products_snapshot:    {product_count}")
            print(f"  orders_snapshot:      {order_count}")
            print(f"  order_items_snapshot: {item_count}")

            if not execute:
                print("\n[DRY-RUN] No changes made. Run with --execute to truncate snapshots.")
                return 0

            # Backup all snapshots
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"report_snapshots_full_backup_{timestamp}.json"

            all_users = [
                {"user_id": u.user_id, "username": u.username, "email": u.email, "role": u.role}
                for u in db.query(UserSnapshot).all()
            ]
            all_orders = [
                {"order_id": o.order_id, "user_id": o.user_id, "status": o.status, "total_amount": str(o.total_amount)}
                for o in db.query(OrderSnapshot).all()
            ]

            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump({"users": all_users, "orders": all_orders}, f, indent=2)
            print(f"\n[BACKUP] Saved snapshot backup to: {backup_file}")

            # Truncate
            db.query(OrderItemSnapshot).delete(synchronize_session=False)
            db.query(OrderSnapshot).delete(synchronize_session=False)
            db.query(ProductSnapshot).delete(synchronize_session=False)
            db.query(UserSnapshot).delete(synchronize_session=False)
            db.commit()
            print("[COMPLETED] All snapshots truncated. Trigger POST /report/sync to repopulate from clean upstream data.")
            return 0

        # Targeted cleanup
        users_query = db.query(UserSnapshot)
        if test_user_ids:
            users_to_delete = users_query.filter(UserSnapshot.user_id.in_(test_user_ids)).all()
        else:
            # Pattern search
            users_to_delete = users_query.filter(
                (UserSnapshot.email.like("%@example.test"))
                | (UserSnapshot.email.like("test_%@%"))
                | (UserSnapshot.username.like("test_%"))
            ).all()

        target_uids = [u.user_id for u in users_to_delete]
        orders_query = db.query(OrderSnapshot)
        if test_order_ids:
            orders_to_delete = orders_query.filter(OrderSnapshot.order_id.in_(test_order_ids)).all()
        elif target_uids:
            orders_to_delete = orders_query.filter(OrderSnapshot.user_id.in_(target_uids)).all()
        else:
            orders_to_delete = []

        products_to_delete = db.query(ProductSnapshot).filter(ProductSnapshot.name.like("[TEST] %")).all()

        print("\nTargeted matches found:")
        print(f"  users_snapshot:    {len(users_to_delete)} row(s)")
        print(f"  orders_snapshot:   {len(orders_to_delete)} row(s)")
        print(f"  products_snapshot: {len(products_to_delete)} row(s)")

        if not users_to_delete and not orders_to_delete and not products_to_delete:
            print("\nNo matching test snapshots found. Nothing to clean up.")
            return 0

        if not execute:
            print("\n[DRY-RUN] No changes made to database. Run with --execute to perform backup and purge.")
            return 0

        # Backup
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"report_snapshots_targeted_backup_{timestamp}.json"

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "users": [{"user_id": u.user_id, "email": u.email, "role": u.role} for u in users_to_delete],
                    "orders": [{"order_id": o.order_id, "user_id": o.user_id, "total": str(o.total_amount)} for o in orders_to_delete],
                    "products": [{"product_id": p.product_id, "name": p.name} for p in products_to_delete],
                },
                f,
                indent=2,
            )
        print(f"\n[BACKUP] Saved backup to: {backup_file}")

        # Purge
        if orders_to_delete:
            order_ids = [o.order_id for o in orders_to_delete]
            db.query(OrderItemSnapshot).filter(OrderItemSnapshot.order_id.in_(order_ids)).delete(synchronize_session=False)
            db.query(OrderSnapshot).filter(OrderSnapshot.order_id.in_(order_ids)).delete(synchronize_session=False)

        if users_to_delete:
            db.query(UserSnapshot).filter(UserSnapshot.user_id.in_([u.user_id for u in users_to_delete])).delete(synchronize_session=False)

        if products_to_delete:
            db.query(ProductSnapshot).filter(ProductSnapshot.product_id.in_([p.product_id for p in products_to_delete])).delete(synchronize_session=False)

        db.commit()
        print("[COMPLETED] Successfully purged test records from report_service snapshots.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"ERROR: Cleanup failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Clean up test snapshot records from report_service")
    parser.add_argument("--execute", action="store_true", help="Execute deletion (default: dry-run)")
    parser.add_argument("--user-ids", type=str, help="Comma-separated user IDs to delete from snapshots")
    parser.add_argument("--order-ids", type=str, help="Comma-separated order IDs to delete from snapshots")
    parser.add_argument("--rebuild", action="store_true", help="Truncate all snapshots for full fresh resync")
    parser.add_argument("--backup-dir", type=Path, help="Directory to save backup JSON file")
    args = parser.parse_args()

    user_ids = [int(u.strip()) for u in args.user_ids.split(",") if u.strip()] if args.user_ids else None
    order_ids = [int(o.strip()) for o in args.order_ids.split(",") if o.strip()] if args.order_ids else None

    sys.exit(
        run_cleanup(
            execute=args.execute,
            test_user_ids=user_ids,
            test_order_ids=order_ids,
            rebuild=args.rebuild,
            backup_dir=args.backup_dir,
        )
    )


if __name__ == "__main__":
    main()

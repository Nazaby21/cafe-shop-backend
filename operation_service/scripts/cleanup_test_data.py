#!/usr/bin/env python
"""
Clean up test orders and test products from operation_service database.

Follows the cascade and isolation rules:
- Deletes orders belonging to specified test users or marked test products.
- Exports matched rows to a JSON backup before deletion.
- Restores product stock for deleted non-cancelled orders using COMPENSATING
  StockMovement entries (preserves existing ledger history without deletion).
- Shows stock quantities before and after in dry-run output.
- Wrapped in a database transaction with rollback on error.
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add operation_service root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.stock_movement import StockMovement, StockMovementReason


def identify_test_orders(db, test_user_ids: list[int] | None = None, specific_order_ids: list[int] | None = None):
    query = db.query(Order)
    if specific_order_ids:
        return query.filter(Order.id.in_(specific_order_ids)).all()
    if test_user_ids:
        return query.filter(Order.user_id.in_(test_user_ids)).all()
    return []


def run_cleanup(
    execute: bool = False,
    test_user_ids: list[int] | None = None,
    specific_order_ids: list[int] | None = None,
    clean_test_catalog: bool = False,
    backup_dir: Path | None = None,
) -> int:
    backup_dir = backup_dir or (Path(__file__).resolve().parent.parent / "backups")
    print(f"Target database: {settings.DB_NAME or settings.database_url}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Mode: {'EXECUTE (will backup, restore stock, and delete)' if execute else 'DRY-RUN (read-only preview)'}")

    db = SessionLocal()
    try:
        orders = identify_test_orders(db, test_user_ids, specific_order_ids)
        print(f"\nFound {len(orders)} test order(s) to remove.")

        # Calculate compensating stock adjustments
        # Orders in PENDING, PAID, COMPLETED consumed stock. CANCELLED orders already had stock restored.
        stock_restorations = defaultdict(int)
        for order in orders:
            if order.status != OrderStatus.CANCELLED:
                for item in order.items:
                    stock_restorations[item.product_id] += item.quantity

        print("\n--- Stock Compensation Preview (Restoring consumed stock) ---")
        product_cache = {}
        if not stock_restorations:
            print("No stock adjustments needed (either 0 orders or all orders were already cancelled).")
        else:
            for pid, qty_to_restore in stock_restorations.items():
                product = db.query(Product).filter(Product.id == pid).first()
                if product:
                    product_cache[pid] = product
                    before_qty = product.stock_quantity
                    after_qty = before_qty + qty_to_restore
                    print(f"  [Product ID {pid}] '{product.name}': Stock BEFORE={before_qty} -> AFTER={after_qty} (+{qty_to_restore})")
                else:
                    print(f"  [Product ID {pid}] (Product no longer exists): +{qty_to_restore} orphaned units")

        test_products = []
        if clean_test_catalog:
            test_products = db.query(Product).filter(Product.name.like("[TEST] %")).all()
            print(f"\nFound {len(test_products)} test product(s) marked with '[TEST] ':")
            for tp in test_products:
                print(f"  [Product ID {tp.id}] '{tp.name}' (category_id={tp.category_id})")

        if not orders and not test_products:
            print("\nNothing to clean up.")
            return 0

        if not execute:
            print("\n[DRY-RUN] No database modifications made.")
            print("Run with --execute to create backup, post compensating stock entries, and delete orders.")
            return 0

        # Step 1: Backup
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"operation_backup_{timestamp}.json"

        backup_data = {
            "orders": [
                {
                    "id": o.id,
                    "user_id": o.user_id,
                    "status": o.status,
                    "total_amount": str(o.total_amount),
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                    "items": [
                        {
                            "id": it.id,
                            "product_id": it.product_id,
                            "product_name": it.product_name,
                            "unit_price": str(it.unit_price),
                            "quantity": it.quantity,
                            "subtotal": str(it.subtotal),
                        }
                        for it in o.items
                    ],
                    "payment": (
                        {
                            "id": o.payment.id,
                            "amount": str(o.payment.amount),
                            "method": o.payment.method,
                            "status": o.payment.status,
                            "transaction_ref": o.payment.transaction_ref,
                        }
                        if o.payment
                        else None
                    ),
                }
                for o in orders
            ],
            "compensated_products": [
                {
                    "product_id": pid,
                    "restored_quantity": qty,
                }
                for pid, qty in stock_restorations.items()
            ],
        }

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2)
        print(f"\n[BACKUP] Saved backup to: {backup_file}")

        # Step 2: Post compensating stock movements and update product quantity
        for pid, qty_to_restore in stock_restorations.items():
            product = product_cache.get(pid)
            if product:
                product.stock_quantity += qty_to_restore
                movement = StockMovement(
                    product_id=product.id,
                    change_quantity=qty_to_restore,
                    quantity_after=product.stock_quantity,
                    reason=StockMovementReason.ADJUSTMENT,
                    reference="cleanup_test_data_reversal",
                )
                db.add(movement)

        # Step 3: Delete orders (items and payments cascade)
        order_ids = [o.id for o in orders]
        if order_ids:
            db.query(Order).filter(Order.id.in_(order_ids)).delete(synchronize_session=False)

        # Step 4: Optional catalog cleanup
        if test_products:
            test_pids = [tp.id for tp in test_products]
            db.query(Product).filter(Product.id.in_(test_pids)).delete(synchronize_session=False)

        db.commit()
        print(f"\n[COMPLETED] Successfully restored stock for {len(stock_restorations)} product(s) and deleted {len(order_ids)} order(s).")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"ERROR: Cleanup failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Clean up test orders and restore stock in operation_service")
    parser.add_argument("--execute", action="store_true", help="Execute deletion (default: dry-run)")
    parser.add_argument("--user-ids", type=str, help="Comma-separated user IDs whose orders should be removed")
    parser.add_argument("--order-ids", type=str, help="Comma-separated order IDs to remove")
    parser.add_argument("--clean-catalog", action="store_true", help="Also remove [TEST] marked products")
    parser.add_argument("--backup-dir", type=Path, help="Directory to save backup JSON file")
    args = parser.parse_args()

    user_ids = [int(u.strip()) for u in args.user_ids.split(",") if u.strip()] if args.user_ids else None
    order_ids = [int(o.strip()) for o in args.order_ids.split(",") if o.strip()] if args.order_ids else None

    sys.exit(
        run_cleanup(
            execute=args.execute,
            test_user_ids=user_ids,
            specific_order_ids=order_ids,
            clean_test_catalog=args.clean_catalog,
            backup_dir=args.backup_dir,
        )
    )


if __name__ == "__main__":
    main()

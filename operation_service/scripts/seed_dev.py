#!/usr/bin/env python
"""
Seed script for development in operation_service.

Refuses to run when ENVIRONMENT=production.
Seeds test-marked category and products:
  - Category: [TEST] Beverages
  - Products: [TEST] Americano, [TEST] Latte

Marker convention:
  - Name prefix: [TEST]
"""
import argparse
import sys
from decimal import Decimal
from pathlib import Path

# Add operation_service root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.category import Category
from app.models.product import Product
from app.models.stock_movement import StockMovementReason
from app.services.stock_service import StockService

TEST_CATEGORY_NAME = "[TEST] Beverages"
TEST_PRODUCTS = [
    {
        "name": "[TEST] Americano",
        "description": "Rich espresso diluted with hot water",
        "price": Decimal("3.50"),
        "initial_stock": 50,
    },
    {
        "name": "[TEST] Latte",
        "description": "Espresso with steamed milk",
        "price": Decimal("4.50"),
        "initial_stock": 40,
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
    stock_service = StockService()
    try:
        category = db.query(Category).filter(Category.name == TEST_CATEGORY_NAME).first()
        if not category:
            print(f"  [TO CREATE] Category {TEST_CATEGORY_NAME}")
        else:
            print(f"  [EXISTS] Category {TEST_CATEGORY_NAME} (id={category.id})")

        products_to_create = []
        for p in TEST_PRODUCTS:
            existing = db.query(Product).filter(Product.name == p["name"]).first()
            if existing:
                print(f"  [EXISTS] Product {p['name']} (id={existing.id}, stock={existing.stock_quantity})")
            else:
                products_to_create.append(p)
                print(f"  [TO CREATE] Product {p['name']} (price={p['price']}, initial_stock={p['initial_stock']})")

        if not category and not products_to_create:
            print("Nothing to seed.")
            return 0

        if dry_run:
            print(f"\nDry-run complete: would create 1 category (if needed) and {len(products_to_create)} product(s).")
            return 0

        if not category:
            category = Category(name=TEST_CATEGORY_NAME, description="Test category for dev")
            db.add(category)
            db.flush()

        for p in products_to_create:
            product = Product(
                name=p["name"],
                description=p["description"],
                price=p["price"],
                stock_quantity=0,
                is_active=True,
                category_id=category.id,
            )
            db.add(product)
            db.flush()

            if p["initial_stock"] > 0:
                stock_service.increase(
                    db,
                    product,
                    p["initial_stock"],
                    reason=StockMovementReason.RESTOCK,
                    reference="initial_dev_seed",
                    commit=False,
                )

        db.commit()
        print(f"\nSuccessfully seeded category and {len(products_to_create)} product(s).")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"ERROR: Seeding failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed development catalog in operation_service")
    parser.add_argument("--execute", action="store_true", help="Execute changes (default: dry-run)")
    args = parser.parse_args()
    sys.exit(seed(dry_run=not args.execute))


if __name__ == "__main__":
    main()

from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exception import SyncFailed
from app.core.security import create_service_token
from app.models.snapshot import OrderItemSnapshot, OrderSnapshot, ProductSnapshot, UserSnapshot


class SyncService:
    """
    The only piece of inter-service communication in this system: pulls the
    latest users / products / orders from user_service and operation_service
    over their public HTTP APIs (authenticated with a short-lived internal
    service token, see core/security.create_service_token) and upserts them
    into report_service's own database.

    report_service never talks to the other services' databases directly.
    """

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {create_service_token()}"}

    def _paginate(self, base_url: str, path: str, params: dict | None = None):
        """Yields every item across all pages of a paginated ApiResponse endpoint."""
        page = 1
        params = dict(params or {})
        try:
            with httpx.Client(base_url=base_url, timeout=10.0) as client:
                while True:
                    params.update({"page": page, "page_size": settings.SYNC_PAGE_SIZE})
                    response = client.get(path, params=params, headers=self._headers())
                    response.raise_for_status()
                    payload = response.json()["data"]
                    for item in payload["items"]:
                        yield item

                    total_pages = payload["meta"]["total_pages"]
                    if page >= total_pages:
                        break
                    page += 1
        except httpx.HTTPError as exc:
            raise SyncFailed(base_url, str(exc))

    # ------------------------------------------------------------- users
    def sync_users(self, db: Session) -> int:
        count = 0
        for u in self._paginate(settings.USER_SERVICE_BASE_URL, "/user"):
            existing = db.get(UserSnapshot, u["id"])
            created_at = datetime.fromisoformat(u["created_at"])
            if existing:
                existing.username = u["username"]
                existing.email = u["email"]
                existing.role = u["role"]
                existing.is_active = u["is_active"]
                existing.created_at = created_at
                existing.synced_at = datetime.now()
            else:
                db.add(
                    UserSnapshot(
                        user_id=u["id"],
                        username=u["username"],
                        email=u["email"],
                        role=u["role"],
                        is_active=u["is_active"],
                        created_at=created_at,
                        synced_at=datetime.now(),
                    )
                )
            count += 1
        db.commit()
        return count

    # ---------------------------------------------------------- products
    def sync_products(self, db: Session) -> int:
        count = 0
        for p in self._paginate(settings.OPERATION_SERVICE_BASE_URL, "/product", params={"active_only": False}):
            existing = db.get(ProductSnapshot, p["id"])
            if existing:
                existing.name = p["name"]
                existing.price = p["price"]
                existing.stock_quantity = p["stock_quantity"]
                existing.is_active = p["is_active"]
                existing.synced_at = datetime.now()
            else:
                db.add(
                    ProductSnapshot(
                        product_id=p["id"],
                        name=p["name"],
                        price=p["price"],
                        stock_quantity=p["stock_quantity"],
                        is_active=p["is_active"],
                        synced_at=datetime.now(),
                    )
                )
            count += 1
        db.commit()
        return count

    # ------------------------------------------------------------ orders
    def sync_orders(self, db: Session) -> int:
        count = 0
        for o in self._paginate(settings.OPERATION_SERVICE_BASE_URL, "/order"):
            existing = db.get(OrderSnapshot, o["id"])
            created_at = datetime.fromisoformat(o["created_at"])
            if existing:
                existing.user_id = o["user_id"]
                existing.status = o["status"]
                existing.total_amount = o["total_amount"]
                existing.created_at = created_at
                existing.synced_at = datetime.now()
                existing.items.clear()
            else:
                existing = OrderSnapshot(
                    order_id=o["id"],
                    user_id=o["user_id"],
                    status=o["status"],
                    total_amount=o["total_amount"],
                    created_at=created_at,
                    synced_at=datetime.now(),
                )
                db.add(existing)
                db.flush()

            for item in o["items"]:
                db.add(
                    OrderItemSnapshot(
                        order_id=o["id"],
                        product_id=item["product_id"],
                        product_name=item["product_name"],
                        unit_price=item["unit_price"],
                        quantity=item["quantity"],
                        subtotal=item["subtotal"],
                    )
                )
            count += 1
        db.commit()
        return count

    def sync_all(self, db: Session) -> dict:
        return {
            "users_synced": self.sync_users(db),
            "products_synced": self.sync_products(db),
            "orders_synced": self.sync_orders(db),
        }

# Service and Repository Analysis

## Architecture Pattern

All three services implement the same **layered architecture**:

```
APIRouter (api/) → Service class (services/) → Repository functions (repository/) → SQLAlchemy model (models/)
```

Dependencies flow downward only. Routers call services; services call repositories; repositories call the ORM. The only cross-service call is `SyncService` in `report_service`, which calls other services over HTTP.

---

## user_service

### UserService

**File:** `user_service/app/services/user_service.py`  
**Instantiation:** Module-level singleton in `user_route.py` (`user_service = UserService()`)  
**Repository dependency:** `user_repository` (imported as `user_repo`)  
**Other dependencies:** `core.security` (hash_password, verify_password, create_access_token), `core.config.settings`

| Method | Signature | Business Logic |
|---|---|---|
| `create_user` | `(db, CreateUserRequest) → User` | Check email uniqueness; strip username; hash password; default role=customer |
| `authenticate` | `(db, LoginRequest) → User` | Lookup by email (soft-delete aware); verify bcrypt; check is_active |
| `issue_token_for` | `(User) → (str, int)` | Create JWT with sub=id, email, role; return token + expiry minutes |
| `get_all_user` | `(db, page, page_size) → (list[User], dict)` | Page-size clamped 1–100; calls count_all + get_all; returns items + meta dict |
| `get_user_by_id` | `(db, user_id) → User` | Raise UserNotFound if None |
| `update_user` | `(db, user_id, UpdateUserRequest) → User` | Fetch user; check email uniqueness if changed; strip username; persist |
| `update_role` | `(db, user_id, role) → User` | Fetch + set role; persist |
| `change_password` | `(db, user_id, ChangePasswordRequest) → User` | Verify old password (InvalidCredentials if wrong); hash new password; persist |
| `delete_user` | `(db, user_id) → User` | Fetch user; soft_delete (sets deleted_at + is_active=False) |

**Transaction handling:** `user_repository.create`, `update`, `soft_delete` each call `db.commit()` internally. No explicit transaction blocks in the service.

---

### user_repository

**File:** `user_service/app/repository/user_repository.py`  
**Style:** Module-level functions (not a class)

| Function | Signature | SQL Behaviour |
|---|---|---|
| `get_by_email` | `(db, email) → User | None` | `WHERE email=? AND deleted_at IS NULL` |
| `create` | `(db, user) → User` | `db.add → commit → refresh` |
| `get_all` | `(db, skip, limit) → list[User]` | `WHERE deleted_at IS NULL ORDER BY id OFFSET skip LIMIT limit` |
| `count_all` | `(db) → int` | `WHERE deleted_at IS NULL` |
| `get_by_id` | `(db, user_id) → User | None` | `WHERE id=? AND deleted_at IS NULL` |
| `update` | `(db, user) → User` | `commit → refresh` (mutation on ORM object before call) |
| `soft_delete` | `(db, user) → User` | Sets `deleted_at=now()`, `is_active=False`, then `commit → refresh` |

---

### user_route (APIRouter)

**File:** `user_service/app/api/user_route.py`  
**Prefix:** `/user`  
**Dependencies:** `get_db`, `get_current_user`, `require_roles`

| Handler | Endpoint | Auth Logic |
|---|---|---|
| `register` | `POST /user` | No auth |
| `login` | `POST /user/login` | No auth |
| `get_me` | `GET /user/me` | `get_current_user` (any role) |
| `read_all_users` | `GET /user` | `require_roles("admin","staff")` |
| `get_user` | `GET /user/{user_id}` | `get_current_user` + inline self-or-role check |
| `update_user` | `PUT /user/{user_id}` | `get_current_user` + inline self-or-admin check |
| `update_user_role` | `PATCH /user/{user_id}/role` | `require_roles("admin")` |
| `change_password` | `PATCH /user/{user_id}/password` | `get_current_user` + inline self-only check |
| `delete_user` | `DELETE /user/{user_id}` | `require_roles("admin")` |

---

## operation_service

### ProductService

**File:** `operation_service/app/services/product_service.py`  
**Dependencies:** `product_repository`, `StockService` (owned instance)

| Method | Logic |
|---|---|
| `add_product` | Check name uniqueness; create product with stock=0; if `initial_stock > 0`, call `StockService.increase` with reason=`restock`, reference=`"initial_stock"` |
| `list_products` | Paginated; supports `active_only` filter |
| `get_product_by_id` | Raise `ProductNotFound` if not found |
| `update_product` | Fetch; check name uniqueness if changed; update fields; persist |
| `adjust_stock` | Delegate to `StockService.adjust` with request fields |
| `deactivate` | Fetch; set `is_active=False`; persist *(note: does not set `deleted_at`)* |

---

### StockService

**File:** `operation_service/app/services/stock_service.py`  
**Design:** Single choke-point for all stock mutations — no code outside this class should modify `Product.stock_quantity` directly.

| Method | Logic |
|---|---|
| `increase(db, product, quantity, reason, reference, commit=True)` | Validates quantity>0; adds to stock; calls `product_repo.update`; records `StockMovement` |
| `decrease(db, product, quantity, reason, reference, commit=True)` | Validates quantity>0; checks `stock_quantity >= quantity` (raises `InsufficientStock`); subtracts; records movement |
| `adjust(db, product, change_quantity, reason, reference, commit=True)` | Routes to `increase` or `decrease` based on sign; raises `InvalidStockAdjustment` if zero |
| `_record_movement(db, product, change_quantity, reason, reference, commit)` | Creates `StockMovement` with `quantity_after = product.stock_quantity` |

**Transaction contract:** `commit=False` is used by `OrderService.create_order` to bundle stock decrements + order insert in one atomic transaction. Standalone API calls (restock endpoint) use `commit=True` (default).

---

### OrderService

**File:** `operation_service/app/services/order_service.py`  
**Dependencies:** `order_repository`, `product_repository`, `StockService`

| Method | Logic |
|---|---|
| `create_order(db, user_id, CreateOrderRequest)` | Validates non-empty items; begins transaction: `db.flush()` to get order.id; for each item: row-lock product (`FOR UPDATE`), check active, call `StockService.decrease(commit=False)`, build `OrderItem`; set `total_amount`; `db.commit()`. On any exception: `db.rollback()` then re-raise. |
| `list_orders(db, page, page_size, user_id, status)` | Paginated; `user_id` filter → customer own orders; `status` filter |
| `get_order_by_id(db, order_id)` | Raise `OrderNotFound` if None |
| `update_status(db, order_id, new_status)` | Validate transition via `OrderStatus.TRANSITIONS`; if `cancelled`, call `_restock_items`; commit. On exception: rollback. |
| `_restock_items(db, order)` | For each item: row-lock product, call `StockService.increase(commit=False)`. Skips items whose product was deleted. |

**N+1 risk:** `Order.items` is loaded with `lazy="selectin"` (batched single additional query), which avoids per-item N+1.

**Critical business rule:** `_restock_items` skips products that no longer exist (`product is None: continue`) — if a product is hard-deleted after an order is placed, cancelling that order silently skips restocking it. In practice this can't happen since only soft-deactivate is used, but it's worth noting.

---

### PaymentService

**File:** `operation_service/app/services/payment_service.py`  
**Dependencies:** `payment_repository`, `OrderService`

| Method | Logic |
|---|---|
| `pay_for_order(db, order_id, CreatePaymentRequest)` | Fetch order via `OrderService`; validate `status==pending`; check for existing `success` payment; call `_charge`; if prior `failed` payment exists, update it; else create new; on success, call `OrderService.update_status(→ paid)` |
| `get_payment_for_order(db, order_id)` | Returns `Payment | None` directly from repo |
| `_charge(amount, method) → (ref, bool, reason)` | Simulated: generates `SIM-<METHOD>-<hex>` ref; returns `(ref, True, None)` unless amount ≤ 0 |

**Issue:** `PaymentService` calls `OrderService.update_status` after `payment_repo.create/update`. Both operations do their own `db.commit()`. If `update_status` fails after payment is persisted, the payment row will exist in `success` state but the order will still be `pending`. This is a potential **state inconsistency bug** in failure scenarios (though rare in the simulated gateway).

---

### Repositories (operation_service)

#### product_repository

| Function | Notes |
|---|---|
| `get_by_name(db, name)` | Soft-delete aware |
| `get_by_id(db, product_id)` | Soft-delete aware |
| `get_by_id_for_update(db, product_id)` | `SELECT ... FOR UPDATE` row lock; used during order creation and cancellation |
| `create(db, product)` | `add → commit → refresh` |
| `update(db, product, commit=True)` | If `commit=False`, uses `db.flush()` instead; allows deferred commit |
| `get_all(db, skip, limit, active_only)` | Supports `active_only` filter; ordered by id |
| `count_all(db, active_only)` | Supports `active_only` filter |

#### order_repository

| Function | Notes |
|---|---|
| `create(db, order)` | `add → commit → refresh` |
| `get_by_id(db, order_id)` | No soft-delete filter (orders are never deleted) |
| `get_by_id_for_user(db, order_id, user_id)` | Additional user_id filter (not used in current router code — router uses `get_by_id` and checks inline) |
| `update(db, order)` | `commit → refresh` |
| `get_all(db, skip, limit, user_id, status)` | Optional filters; ordered `id DESC` |
| `count_all(db, user_id, status)` | Matching filters |

> [!NOTE]
> `get_by_id_for_user` exists in the repository but is **not currently called** by the router or service. The router fetches by `order_id` only and then applies an inline ownership check.

#### payment_repository

| Function | Notes |
|---|---|
| `get_by_order_id(db, order_id)` | Simple filter; returns first match |
| `create(db, payment)` | `add → commit → refresh` |
| `update(db, payment)` | `commit → refresh` |

#### stock_repository

| Function | Notes |
|---|---|
| `create_movement(db, movement, commit=True)` | Respects `commit=False` → `flush()` pattern |
| `get_movements_for_product(db, product_id, skip, limit)` | Ordered `id DESC`; **no API endpoint currently exposes this** |

> [!NOTE]
> `get_movements_for_product` exists but there is no router endpoint to retrieve a product's stock movement history — it is implemented but unexposed.

---

## report_service

### ReportService

**File:** `report_service/app/services/report_service.py`  
**Dependencies:** `sales_report_repository`, `user_report_repository`

| Method | Logic |
|---|---|
| `_validate_range(start, end)` | Raises `InvalidDateRange` if `start > end` |
| `sales_summary(db, start, end)` | Calls 4 repo functions; computes `average_order_value = revenue / (paid+completed)`; returns `SalesSummaryResponse` |
| `daily_sales(db, start, end)` | Calls `daily_sales_in_range`; maps rows to `DailySalesPoint` |
| `top_products(db, start, end, limit)` | Calls `top_products_in_range`; maps rows to `TopProductResponse` |
| `low_stock_alerts(db, threshold)` | Calls `low_stock_products`; maps to `InventoryAlertResponse` |
| `user_summary(db, start, end)` | 4 repo calls; returns `UserSummaryResponse` |

---

### SyncService

**File:** `report_service/app/services/sync_service.py`  
**Dependencies:** `httpx.Client` (blocking HTTP), `core.security.create_service_token`

| Method | Logic |
|---|---|
| `_headers()` | Generates fresh service token each call (short-lived, 5-minute default) |
| `_paginate(base_url, path, params)` | Iterates pages until `page >= total_pages`; raises `SyncFailed` on HTTP errors |
| `sync_users(db)` | Paginates `GET /user`; upserts `UserSnapshot` (get by PK → update or create); commits per-resource-type |
| `sync_products(db)` | Paginates `GET /product?active_only=False`; upserts `ProductSnapshot` |
| `sync_orders(db)` | Paginates `GET /order`; upserts `OrderSnapshot` + replaces `OrderItemSnapshot` (clears existing items on update) |
| `sync_all(db)` | Calls `sync_users`, `sync_products`, `sync_orders`; returns counts dict |

**Blocking HTTP:** `httpx.Client` is synchronous. Since FastAPI endpoints are synchronous (`def`, not `async def`), this is acceptable but blocks the event loop thread.

**Data consistency risk:** `sync_orders` calls `existing.items.clear()` then re-adds items. If the `db.flush()` or `db.commit()` after adding new items fails, items are already cleared — potential data loss in the snapshot (non-critical since snapshot is rebuildable).

---

### Repositories (report_service)

#### sales_report_repository

| Function | Query |
|---|---|
| `count_orders_in_range` | `COUNT(*)` on `orders_snapshot` by `created_at` range |
| `count_orders_by_status_in_range` | Same + status filter |
| `total_revenue_in_range` | `SUM(total_amount)` for `paid`/`completed` orders in range |
| `daily_sales_in_range` | `GROUP BY date(created_at)` for `paid`/`completed`; returns `(day, count, sum)` tuples |
| `top_products_in_range` | JOIN `order_items_snapshot` on `orders_snapshot`; `GROUP BY product_id, product_name`; ordered by `SUM(quantity) DESC`; LIMIT |
| `low_stock_products` | `WHERE is_active=True AND stock_quantity <= threshold ORDER BY stock_quantity ASC` |
| `last_synced_at` | `MAX(synced_at)` — **not currently called by any service or endpoint** |

#### user_report_repository

| Function | Query |
|---|---|
| `count_total` | `COUNT(*)` on `users_snapshot` |
| `count_active` | `WHERE is_active=True` |
| `count_new_in_range` | `WHERE created_at BETWEEN start AND end` |
| `count_by_role` | `GROUP BY role` → dict |
| `last_synced_at` | `MAX(synced_at)` — **not currently exposed** |

---

## Request Processing Flow

### Example: `POST /order` (Create Order)

```
Client → POST /order (Bearer token)
  ↓
FastAPI matches route → order_route.create_order
  ↓
Dependency: get_db (yields SQLAlchemy Session)
Dependency: get_current_user (decodes JWT → CurrentUser{id, email, role})
  ↓
Pydantic: CreateOrderRequest validated (items non-empty, quantity > 0)
  ↓
order_service.create_order(db, user_id=current_user.id, request)
  ↓
  [BEGIN implicit SQLAlchemy transaction]
  Order(user_id, status="pending", total_amount=0) → db.add → db.flush (get order.id)
  For each item:
    product_repo.get_by_id_for_update(db, item.product_id)  [SELECT FOR UPDATE]
    Check product exists and is_active
    stock_service.decrease(db, product, quantity, reason="sale", reference="order#N", commit=False)
      → product.stock_quantity -= quantity
      → product_repo.update(db, product, commit=False)  [db.flush()]
      → stock_repo.create_movement(db, movement, commit=False) [db.flush()]
    Build OrderItem → db.add
  order.total_amount = total_amount
  db.commit()
  db.refresh(order)
  ↓
ApiResponse(success=True, data=order)
  ↓
Pydantic: OrderResponse serialized (order + nested items via selectin)
  ↓
200 JSON response
```

On any exception between `db.add(order)` and `db.commit()`: `except Exception: db.rollback(); raise` ensures all stock decrements are undone.

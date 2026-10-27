# API Documentation

## Standard Response Envelope

All endpoints return:

```json
{ "success": true|false, "error_code": null|"string", "message": "...", "data": { } }
```

Paginated responses wrap `data` as:
```json
{
  "data": {
    "items": [ ... ],
    "meta": { "page": 1, "page_size": 20, "total_items": 53, "total_pages": 3 }
  }
}
```

---

## user_service — Port 8001

### Complete Endpoint Inventory

| Method | Endpoint | Auth Required | Roles Allowed | Description |
|---|---|---|---|---|
| POST | `/user` | No | Public | Register a new user |
| POST | `/user/login` | No | Public | Login, receive JWT |
| GET | `/user/me` | Yes | Any authenticated | Get own profile |
| GET | `/user` | Yes | admin, staff | Paginated user list |
| GET | `/user/{user_id}` | Yes | Self or admin/staff | Get a specific user |
| PUT | `/user/{user_id}` | Yes | Self or admin | Update username/email/is_active |
| PATCH | `/user/{user_id}/role` | Yes | admin only | Promote/demote role |
| PATCH | `/user/{user_id}/password` | Yes | Self only | Change own password |
| DELETE | `/user/{user_id}` | Yes | admin only | Soft-delete user |

---

### `POST /user` — Register

**Authentication:** Not required  
**Router:** `user_service/app/api/user_route.py`

**Request body:**
```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "supersecret1"
}
```

| Field | Type | Validation |
|---|---|---|
| `username` | string | min_length=1, max_length=255 |
| `email` | EmailStr | Valid email format |
| `password` | string | min_length=8, max_length=72 |

**Success Response (200):**
```json
{
  "success": true,
  "error_code": null,
  "message": "User registered successfully",
  "data": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "role": "customer",
    "is_active": true,
    "created_at": "2026-10-01T10:00:00"
  }
}
```

**Error Responses:**

| Status | error_code | Condition |
|---|---|---|
| 409 | `err_409` | Email already exists |
| 422 | — (Pydantic) | Validation error |

---

### `POST /user/login` — Login

**Authentication:** Not required

**Request body:**
```json
{ "email": "alice@example.com", "password": "supersecret1" }
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "<JWT>",
    "token_type": "bearer",
    "expires_in_minutes": 60,
    "user": { "id": 1, "username": "alice", "email": "alice@example.com", "role": "customer", "is_active": true, "created_at": "..." }
  }
}
```

**Error Responses:**

| Status | error_code | Condition |
|---|---|---|
| 401 | `err_401_invalid_credentials` | Wrong email or password |
| 403 | `err_403` | Account is deactivated |

---

### `GET /user/me` — Get own profile

**Authentication:** Bearer token (any role)

**Success Response (200):** `data` = `UserResponse` object.

**Error Responses:**

| Status | error_code | Condition |
|---|---|---|
| 401 | `err_401` | Missing or invalid token |
| 401 | `err_401_token_expired` | Token expired |
| 403 | `err_403_inactive_user` | Account deactivated |

---

### `GET /user` — List users (paginated)

**Authentication:** Bearer token  
**Roles:** admin, staff

**Query parameters:**

| Param | Type | Default | Validation |
|---|---|---|---|
| `page` | int | 1 | ge=1 |
| `page_size` | int | 20 | ge=1, le=100 |

**Success Response (200):** `data` = `PaginatedData[UserResponse]`

**Error Responses:** 401, 403 (insufficient role)

---

### `GET /user/{user_id}` — Get user by ID

**Authentication:** Bearer token  
**Authorization:** Self (own ID) OR admin/staff (checked inline in router)

**Path parameters:** `user_id: int`

**Success Response (200):** `data` = `UserResponse`

**Error Responses:**

| Status | error_code | Condition |
|---|---|---|
| 403 | `err_403` | Not self and not admin/staff |
| 404 | `err_404` | User not found |

---

### `PUT /user/{user_id}` — Update user

**Authentication:** Bearer token  
**Authorization:** Self OR admin (checked inline in router; staff cannot update other users)

**Request body:**
```json
{ "username": "alice-updated", "email": "alice@example.com", "is_active": true }
```

| Field | Type | Validation |
|---|---|---|
| `username` | string | min_length=1, max_length=255 |
| `email` | EmailStr | Valid format |
| `is_active` | bool | Default: `true` |

**Success Response (200):** `data` = `UserResponse`

**Error Responses:** 403, 404, 409 (email conflict)

---

### `PATCH /user/{user_id}/role` — Update role

**Authentication:** Bearer token  
**Roles:** admin only

**Request body:**
```json
{ "role": "staff" }
```

| Field | Validation |
|---|---|
| `role` | pattern `^(customer\|staff\|admin)$` |

**Success Response (200):** `data` = `UserResponse`

---

### `PATCH /user/{user_id}/password` — Change password

**Authentication:** Bearer token  
**Authorization:** Self only (checked inline — cannot change another user's password)

**Request body:**
```json
{ "old_password": "supersecret1", "new_password": "evenmoresecret2" }
```

| Field | Validation |
|---|---|
| `old_password` | string |
| `new_password` | min_length=8, max_length=72 |

**Error Responses:** 401 (wrong old password), 403 (not self), 404

---

### `DELETE /user/{user_id}` — Soft-delete user

**Authentication:** Bearer token  
**Roles:** admin only

**Success Response (200):** `data` = `UserResponse` (with `is_active=false`, `deleted_at` populated)

---

## operation_service — Port 8002

### Complete Endpoint Inventory

| Method | Endpoint | Auth | Roles | Description |
|---|---|---|---|---|
| POST | `/product` | Yes | admin, staff | Add a product |
| GET | `/product` | No | Public | Paginated product list |
| GET | `/product/{product_id}` | No | Public | Get single product |
| PUT | `/product/{product_id}` | Yes | admin, staff | Update product |
| POST | `/product/{product_id}/stock` | Yes | admin, staff | Adjust stock |
| DELETE | `/product/{product_id}` | Yes | admin, staff | Deactivate product |
| POST | `/order` | Yes | Any | Create order |
| GET | `/order` | Yes | Any | List orders |
| GET | `/order/{order_id}` | Yes | Owner or admin/staff | Get single order |
| PATCH | `/order/{order_id}/status` | Yes | admin, staff | Update order status |
| POST | `/order/{order_id}/cancel` | Yes | Owner or admin/staff | Cancel own order |
| POST | `/order/{order_id}/payment` | Yes | Owner or admin/staff | Pay for order |
| GET | `/order/{order_id}/payment` | Yes | Owner or admin/staff | Get payment status |

---

### Product Endpoints

#### `POST /product` — Add product

**Request body:**
```json
{
  "name": "Cappuccino",
  "description": "Espresso with steamed milk foam",
  "price": 4.00,
  "initial_stock": 25
}
```

| Field | Validation |
|---|---|
| `name` | min_length=1, max_length=255 |
| `description` | optional, max_length=1000 |
| `price` | Decimal, gt=0 |
| `initial_stock` | int, ge=0, default=0 |

**Success Response (200):** `data` = `ProductResponse`

**Error Responses:** 409 (`err_409_product_name` — name conflict)

#### `GET /product` — List products

**No authentication required.**

**Query parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `page` | int | 1 | ge=1 |
| `page_size` | int | 20 | ge=1, le=100 |
| `active_only` | bool | false | Filter to is_active=True only |

**Success Response (200):** `data` = `PaginatedData[ProductResponse]`

#### `GET /product/{product_id}` — Get product

**No authentication required.**  
**Error:** 404 (`err_404_product`)

#### `PUT /product/{product_id}` — Update product

**Request body:**
```json
{ "name": "Cappuccino", "description": "Updated desc", "price": 4.25, "is_active": true }
```

| Field | Validation |
|---|---|
| `name` | min_length=1, max_length=255 |
| `description` | optional |
| `price` | Decimal, gt=0 |
| `is_active` | bool, default=True |

#### `POST /product/{product_id}/stock` — Adjust stock

**Request body:**
```json
{ "change_quantity": 10, "reason": "restock", "reference": "supplier delivery #45" }
```

| Field | Validation |
|---|---|
| `change_quantity` | int (positive=add, negative=remove) |
| `reason` | pattern `^(restock\|adjustment)$` |
| `reference` | optional, max_length=255 |

**Error Responses:** 409 (`err_409_insufficient_stock`), 400 (`err_400_stock_adjustment`)

#### `DELETE /product/{product_id}` — Deactivate product

Sets `is_active=False`. **Does not set `deleted_at`** — this is a deactivation, not a soft-delete in the same sense as users.

---

### Order Endpoints

#### `POST /order` — Create order

**Authentication:** Any authenticated user

**Request body:**
```json
{
  "items": [
    { "product_id": 1, "quantity": 2 },
    { "product_id": 3, "quantity": 1 }
  ]
}
```

| Field | Validation |
|---|---|
| `items` | list, min_length=1 |
| `items[].product_id` | int |
| `items[].quantity` | int, gt=0 |

**Business rules (enforced transactionally):**
- Each product must exist and be active
- Each product must have sufficient stock (row-locked with `SELECT FOR UPDATE`)
- Stock decremented atomically; any failure rolls back all decrements

**Success Response (200):** `data` = `OrderResponse`

**Error Responses:**

| Status | error_code | Condition |
|---|---|---|
| 400 | `err_400_empty_order` | Empty items list |
| 404 | `err_404_product` | Product not found |
| 409 | `err_409_product_inactive` | Product not active |
| 409 | `err_409_insufficient_stock` | Not enough stock |

#### `GET /order` — List orders

**Authentication:** Any authenticated user  
**Behavior:** Customers only see their own orders; admin/staff see all.

**Query parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `page` | int | 1 | ge=1 |
| `page_size` | int | 20 | ge=1, le=100 |
| `status` | string | None | pattern `^(pending\|paid\|cancelled\|completed)$` |

#### `GET /order/{order_id}` — Get order

**Authorization:** Owner OR admin/staff (checked inline in router)

#### `PATCH /order/{order_id}/status` — Update order status

**Roles:** admin, staff only

**Request body:**
```json
{ "status": "completed" }
```

| Field | Validation |
|---|---|
| `status` | pattern `^(pending\|paid\|cancelled\|completed)$` |

**Business rules:**
- Validates allowed transition via `OrderStatus.TRANSITIONS`
- On `cancelled`: restocks all items (row-lock + `StockService.increase`)

**Error Responses:**

| Status | error_code | Condition |
|---|---|---|
| 409 | `err_409_order_status` | Invalid status transition |

#### `POST /order/{order_id}/cancel` — Cancel own order

**Authorization:** Owner OR admin/staff  
Internally calls `update_status` with `"cancelled"`.

---

### Payment Endpoints

#### `POST /order/{order_id}/payment` — Pay for order

**Authorization:** Owner OR admin/staff

**Request body:**
```json
{ "method": "card" }
```

| Field | Validation |
|---|---|
| `method` | pattern `^(cash\|card\|e_wallet)$` |

**Business rules:**
- Order must be in `pending` status
- No prior `success` payment may exist
- If a prior `failed` payment exists, it is retried (updated in place)
- Simulated gateway always succeeds for amount > 0
- On success: order status moves to `paid`

**Success Response (200):** `data` = `PaymentResponse`

**Error Responses:**

| Status | error_code | Condition |
|---|---|---|
| 409 | `err_409_order_not_payable` | Order not in `pending` status |
| 409 | `err_409_payment_exists` | Successful payment already recorded |
| 402 | `err_402_payment_failed` | Simulated gateway failure |

#### `GET /order/{order_id}/payment` — Get payment

**Authorization:** Owner OR admin/staff

**Error:** 404 (`err_404_payment`)

---

## report_service — Port 8003

### Complete Endpoint Inventory

| Method | Endpoint | Auth | Roles | Description |
|---|---|---|---|---|
| POST | `/report/sync` | Yes | admin, staff | Pull latest data from other services |
| GET | `/report/sales-summary` | Yes | admin, staff | Sales KPIs for a date range |
| GET | `/report/daily-sales` | Yes | admin, staff | Revenue/orders grouped by day |
| GET | `/report/top-products` | Yes | admin, staff | Best sellers by quantity |
| GET | `/report/low-stock` | Yes | admin, staff | Active products at/below threshold |
| GET | `/report/users-summary` | Yes | admin, staff | User registration and role stats |

**Default date range (all range-based endpoints):** Trailing 30 days when no dates given.

---

### `POST /report/sync` — Trigger sync

**Roles:** admin, staff

**Success Response (200):**
```json
{
  "success": true,
  "message": "Sync completed successfully",
  "data": { "users_synced": 5, "products_synced": 12, "orders_synced": 87 }
}
```

**Error Responses:** 502 (`err_502_sync_failed` — upstream service unreachable)

---

### `GET /report/sales-summary`

**Query parameters:**

| Param | Type | Default |
|---|---|---|
| `start_date` | date (YYYY-MM-DD) | today − 30 days |
| `end_date` | date | today |

**Success Response (200):**
```json
{
  "data": {
    "start_date": "2026-09-01",
    "end_date": "2026-10-01",
    "total_orders": 87,
    "paid_orders": 72,
    "cancelled_orders": 8,
    "total_revenue": "1234.50",
    "average_order_value": "17.15"
  }
}
```

> [!NOTE]
> `paid_orders` in the response actually includes both `paid` AND `completed` orders (the field name is slightly misleading — see `report_service.py` line 34).

---

### `GET /report/daily-sales`

Same date query params. Returns list:
```json
{ "data": [ { "day": "2026-09-15", "order_count": 12, "revenue": "234.00" }, ... ] }
```

---

### `GET /report/top-products`

| Param | Type | Default | Validation |
|---|---|---|---|
| `start_date` | date | today−30d | — |
| `end_date` | date | today | — |
| `limit` | int | 10 | ge=1, le=50 |

```json
{ "data": [ { "product_id": 1, "product_name": "Cappuccino", "quantity_sold": 45, "revenue": "180.00" }, ... ] }
```

---

### `GET /report/low-stock`

| Param | Type | Default | Validation |
|---|---|---|---|
| `threshold` | int | 10 | ge=0 |

Returns active products with `stock_quantity <= threshold`, ordered by stock ascending.

---

### `GET /report/users-summary`

Same date query params.
```json
{
  "data": {
    "total_users": 42,
    "active_users": 40,
    "inactive_users": 2,
    "new_users_in_range": 5,
    "users_by_role": { "customer": 38, "staff": 3, "admin": 1 }
  }
}
```

---

## Common Error Codes Reference

| HTTP Status | error_code | Meaning |
|---|---|---|
| 400 | `err_400_empty_order` | Order submitted with no items |
| 400 | `err_400_stock_adjustment` | Zero-quantity adjustment |
| 400 | `err_400_date_range` | start_date > end_date |
| 401 | `err_401` | Missing bearer token |
| 401 | `err_401_invalid_credentials` | Wrong email/password |
| 401 | `err_401_invalid_token` | Malformed/invalid JWT |
| 401 | `err_401_token_expired` | JWT has expired |
| 402 | `err_402_payment_failed` | Simulated gateway failure |
| 403 | `err_403` | Role insufficient |
| 403 | `err_403_inactive_user` | Account deactivated |
| 404 | `err_404` | User not found |
| 404 | `err_404_product` | Product not found |
| 404 | `err_404_order` | Order not found |
| 404 | `err_404_payment` | Payment not found |
| 409 | `err_409` | Email already exists |
| 409 | `err_409_product_name` | Product name conflict |
| 409 | `err_409_product_inactive` | Product not available |
| 409 | `err_409_insufficient_stock` | Not enough stock |
| 409 | `err_409_order_status` | Invalid status transition |
| 409 | `err_409_order_not_payable` | Order not in payable state |
| 409 | `err_409_payment_exists` | Successful payment already recorded |
| 502 | `err_502_sync_failed` | Upstream service unreachable during sync |

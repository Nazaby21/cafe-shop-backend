# Schema and Validation Analysis

## Shared Schema Pattern

All three services define an identical `api_response.py` with:

```python
class ApiResponse(BaseModel, Generic[T]):
    success: bool
    error_code: Optional[str] = None
    message: str
    data: Optional[T] = None

class PageMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int

class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta
```

This code is **duplicated verbatim** across all three services rather than being shared via a common package.

---

## user_service Schemas

**File:** `user_service/app/schemas/user_schema.py`

### `LoginRequest`

| Field | Type | Validation |
|---|---|---|
| `email` | `EmailStr` | Must be valid email format |
| `password` | `str` | No length constraint on login |

**Used by:** `POST /user/login`

---

### `CreateUserRequest`

| Field | Type | Validation |
|---|---|---|
| `username` | `str` | min_length=1, max_length=255 |
| `email` | `EmailStr` | Valid email |
| `password` | `str` | min_length=8, max_length=72 |

**Used by:** `POST /user`

> [!NOTE]
> `max_length=72` matches bcrypt's internal limit (the `security.py` comment explains the 72-byte truncation explicitly).

---

### `UserResponse`

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | — |
| `username` | `str` | — |
| `email` | `EmailStr` | — |
| `role` | `str` | — |
| `is_active` | `bool` | — |
| `created_at` | `datetime` | — |

**Config:** `model_config = ConfigDict(from_attributes=True)` — enables ORM model → Pydantic conversion.  
**Excluded fields:** `password`, `updated_at`, `deleted_at` — sensitive/internal fields correctly omitted.

---

### `UpdateUserRequest`

| Field | Type | Validation |
|---|---|---|
| `username` | `str` | min_length=1, max_length=255 |
| `email` | `EmailStr` | — |
| `is_active` | `bool` | default=True |

> [!CAUTION]
> `is_active` defaults to `True` in `UpdateUserRequest`. A partial update call that omits `is_active` will always send `True`, potentially **reactivating a deactivated account** inadvertently. This is a potential data integrity issue.

---

### `ChangePasswordRequest`

| Field | Type | Validation |
|---|---|---|
| `old_password` | `str` | No constraint |
| `new_password` | `str` | min_length=8, max_length=72 |

**Used by:** `PATCH /user/{user_id}/password`

---

### `UpdateUserRoleRequest`

| Field | Type | Validation |
|---|---|---|
| `role` | `str` | pattern `^(customer\|staff\|admin)$` |

**Used by:** `PATCH /user/{user_id}/role`

---

### `TokenResponse`

| Field | Type | Notes |
|---|---|---|
| `access_token` | `str` | The JWT |
| `token_type` | `str` | default=`"bearer"` |
| `expires_in_minutes` | `int` | From `settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES` |
| `user` | `UserResponse` | Full user object |

**Used by:** `POST /user/login`

---

## operation_service Schemas

### `CreateProductRequest`

**File:** `operation_service/app/schemas/product_schema.py`

| Field | Type | Validation |
|---|---|---|
| `name` | `str` | min_length=1, max_length=255 |
| `description` | `str | None` | optional, max_length=1000 |
| `price` | `Decimal` | gt=0 |
| `initial_stock` | `int` | default=0, ge=0 |

---

### `UpdateProductRequest`

| Field | Type | Validation |
|---|---|---|
| `name` | `str` | min_length=1, max_length=255 |
| `description` | `str | None` | optional |
| `price` | `Decimal` | gt=0 |
| `is_active` | `bool` | default=True |

> [!NOTE]
> Same `is_active` default=True issue as `UpdateUserRequest` — if `is_active` is omitted, it defaults to `True`, which could reactivate a product.

---

### `AdjustStockRequest`

| Field | Type | Validation |
|---|---|---|
| `change_quantity` | `int` | No Pydantic constraint (zero validated in `StockService.adjust`) |
| `reason` | `str` | default=`"adjustment"`, pattern `^(restock\|adjustment)$` |
| `reference` | `str | None` | optional, max_length=255 |

> [!NOTE]
> The pattern constraint limits `reason` to `restock` or `adjustment` only. The service internally also uses `sale` and `cancellation` reasons, but those are never exposed via this schema — they are set internally by `OrderService`.

---

### `ProductResponse`

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | — |
| `name` | `str` | — |
| `description` | `str | None` | — |
| `price` | `Decimal` | — |
| `stock_quantity` | `int` | — |
| `is_active` | `bool` | — |

**Excluded fields:** `created_at`, `updated_at`, `deleted_at`

---

### `OrderItemRequest`

| Field | Type | Validation |
|---|---|---|
| `product_id` | `int` | — |
| `quantity` | `int` | gt=0 |

---

### `CreateOrderRequest`

| Field | Type | Validation |
|---|---|---|
| `items` | `list[OrderItemRequest]` | min_length=1 |

---

### `UpdateOrderStatusRequest`

| Field | Type | Validation |
|---|---|---|
| `status` | `str` | pattern `^(pending\|paid\|cancelled\|completed)$` |

> [!NOTE]
> The schema allows setting status to `pending` (the initial state), but the service's `update_status` method will reject same-status transitions with no-op (`return order`). This is harmless but slightly inconsistent — the schema could restrict to non-pending values only.

---

### `OrderItemResponse`

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | — |
| `product_id` | `int` | — |
| `product_name` | `str` | Snapshot value |
| `unit_price` | `Decimal` | Snapshot value |
| `quantity` | `int` | — |
| `subtotal` | `Decimal` | — |

---

### `OrderResponse`

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | — |
| `user_id` | `int` | — |
| `status` | `str` | — |
| `total_amount` | `Decimal` | — |
| `created_at` | `datetime` | — |
| `items` | `list[OrderItemResponse]` | Nested; loaded via `selectin` relationship |

**Excluded fields:** `updated_at`, `payment` (payment has its own endpoint)

---

### `CreatePaymentRequest`

| Field | Type | Validation |
|---|---|---|
| `method` | `str` | pattern `^(cash\|card\|e_wallet)$` |

---

### `PaymentResponse`

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | — |
| `order_id` | `int` | — |
| `amount` | `Decimal` | — |
| `method` | `str` | — |
| `status` | `str` | — |
| `transaction_ref` | `str` | Simulated gateway ref |
| `failure_reason` | `str | None` | — |

**Excluded fields:** `created_at`, `updated_at`

---

## report_service Schemas

**File:** `report_service/app/schemas/report_schema.py`

### `SalesSummaryResponse`

| Field | Type |
|---|---|
| `start_date` | `date` |
| `end_date` | `date` |
| `total_orders` | `int` |
| `paid_orders` | `int` |
| `cancelled_orders` | `int` |
| `total_revenue` | `Decimal` |
| `average_order_value` | `Decimal` |

### `DailySalesPoint`

| Field | Type |
|---|---|
| `day` | `date` |
| `order_count` | `int` |
| `revenue` | `Decimal` |

### `TopProductResponse`

| Field | Type |
|---|---|
| `product_id` | `int` |
| `product_name` | `str` |
| `quantity_sold` | `int` |
| `revenue` | `Decimal` |

### `UserSummaryResponse`

| Field | Type |
|---|---|
| `total_users` | `int` |
| `active_users` | `int` |
| `inactive_users` | `int` |
| `new_users_in_range` | `int` |
| `users_by_role` | `dict[str, int]` |

### `InventoryAlertResponse`

| Field | Type |
|---|---|
| `product_id` | `int` |
| `product_name` | `str` |
| `stock_quantity` | `int` |

### `SyncResultResponse`

| Field | Type |
|---|---|
| `users_synced` | `int` |
| `products_synced` | `int` |
| `orders_synced` | `int` |

---

## Validation Analysis

### Validation Strengths

- Pydantic v2 `EmailStr` enforces valid email format on all user inputs
- `Field(pattern=...)` enforces enum-like values for `role`, `status`, `method`, `reason` without requiring Python Enum types
- `Field(gt=0)` on `price` prevents non-positive prices at the API boundary
- `Field(min_length=1)` prevents blank names on products and users
- `Field(ge=0)` on `initial_stock` prevents negative initialization

### Validation Issues

| Issue | Location | Impact |
|---|---|---|
| `is_active` defaults to `True` in update schemas | `UpdateUserRequest`, `UpdateProductRequest` | Partial updates can reactivate deactivated records |
| No `max_length` on `username` in `ChangePasswordRequest` | `user_schema.py` | `old_password` has no length limit (cosmetic only) |
| `UpdateOrderStatusRequest` allows `"pending"` as a target status | `order_schema.py` | Inconsistency (service ignores same-status no-ops) |
| `change_quantity` in `AdjustStockRequest` has no Pydantic non-zero constraint | `product_schema.py` | Zero is rejected by `StockService` but error response is from service layer, not schema layer |
| No input sanitization beyond `strip()` | `user_service.py`, `product_service.py` | Only `username` and `name` are stripped; no sanitization of `description`, `reference`, etc. |
| Report date params have no max range limit | `report_route.py` | A very wide date range can cause expensive queries |

### Serialization Notes

- All response schemas with ORM models use `ConfigDict(from_attributes=True)` (Pydantic v2 pattern)
- `Decimal` fields serialize correctly to JSON strings; clients should treat monetary values as strings or use `Decimal`-aware parsing
- `datetime` fields serialize as ISO 8601 strings without timezone info (naive datetimes from `datetime.now`)
- `dict[str, int]` in `UserSummaryResponse.users_by_role` serializes correctly to a JSON object

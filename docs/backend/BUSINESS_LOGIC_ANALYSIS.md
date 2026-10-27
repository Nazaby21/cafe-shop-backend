# Business Logic Analysis

## Feature Inventory

| Feature | Service | Status | Notes |
|---|---|---|---|
| User registration | user_service | ✅ Complete | Password hashing, email uniqueness, default role=customer |
| User login / JWT issuance | user_service | ✅ Complete | bcrypt verify, JWT generation |
| Profile management | user_service | ✅ Complete | Self-update username/email/is_active |
| Role management | user_service | ✅ Complete | Admin-only PATCH; validates role via regex |
| Password change | user_service | ✅ Complete | Old password verification required |
| User soft-delete | user_service | ✅ Complete | Sets deleted_at + is_active=False |
| User listing (admin/staff) | user_service | ✅ Complete | Paginated, soft-delete aware |
| Product management (CRUD) | operation_service | ✅ Complete | Create, read, update, deactivate |
| Stock management | operation_service | ✅ Complete | StockService choke-point, audit ledger |
| Order creation (with atomicity) | operation_service | ✅ Complete | Transactional, row-locked stock decrement |
| Order listing / filtering | operation_service | ✅ Complete | Role-aware (customers see own only) |
| Order status transitions | operation_service | ✅ Complete | Validated state machine |
| Order cancellation + restock | operation_service | ✅ Complete | Restocks on cancel |
| Payment processing (simulated) | operation_service | ✅ Complete | Simulated gateway, retry on failure |
| Stock movement audit log | operation_service | ✅ Complete | Append-only; all mutations logged |
| Data sync from upstreams | report_service | ✅ Complete | Paginated HTTP pull, upsert |
| Sales summary report | report_service | ✅ Complete | Revenue, order counts, average |
| Daily sales breakdown | report_service | ✅ Complete | Group by day, paid/completed only |
| Top products report | report_service | ✅ Complete | Sorted by quantity, with revenue |
| Low-stock inventory alerts | report_service | ✅ Complete | Configurable threshold |
| User statistics report | report_service | ✅ Complete | Total/active/inactive, by role, new signups |
| Stock movement history API | operation_service | ⚠️ Partial | `get_movements_for_product` repo exists but no endpoint exposes it |
| Real payment gateway | operation_service | ❌ Not implemented | `_charge()` is a simulation stub |
| Alembic migrations | All services | ❌ Not implemented | Installed but unconfigured |
| Scheduled sync (cron) | report_service | ❌ Not implemented | Only startup sync + on-demand |
| Refresh token | All services | ❌ Not implemented | Access tokens only, no refresh |
| Logout / token blacklisting | All services | ❌ Not implemented | Client-side only |
| Email notifications | All services | ❌ Not implemented | No email integration |

---

## Business Workflows

### Workflow 1: User Registration and Login

```
1. Client → POST /user { username, email, password }
   - Email uniqueness checked (409 if duplicate)
   - password hashed with bcrypt
   - User created with role="customer", is_active=True
   - Response: UserResponse

2. Client → POST /user/login { email, password }
   - User fetched by email (must exist and not be soft-deleted)
   - bcrypt verify (401 InvalidCredentials if wrong)
   - is_active checked (403 if deactivated)
   - JWT issued: { sub: user.id, email, role }
   - Response: TokenResponse { access_token, expires_in_minutes, user }

3. Client uses access_token in Authorization: Bearer header for all subsequent calls
```

---

### Workflow 2: Order Creation (Core Business Logic)

```
1. Client → POST /order { items: [{ product_id, quantity }, ...] }
   Token required (any role)

2. For each line item (inside a single transaction):
   a. SELECT product FOR UPDATE  (row-level lock prevents overselling)
   b. Check product exists, is active
   c. Check stock_quantity >= requested quantity
   d. Decrement stock_quantity (no commit yet)
   e. Append StockMovement(reason="sale", reference="order#N") (no commit yet)
   f. Create OrderItem (snapshot product_name + unit_price)
   g. Accumulate total_amount

3. Set order.total_amount, db.commit()
4. ANY exception → db.rollback() (all stock changes undone)

Result: Order in "pending" status, stock decremented
```

---

### Workflow 3: Order Payment

```
1. Client → POST /order/{id}/payment { method: "card" }
   Must be order owner or admin/staff

2. Checks:
   a. Order exists (404 if not)
   b. Caller is owner or admin/staff (403 if not)
   c. Order.status == "pending" (409 OrderNotPayable if not)
   d. No existing "success" payment (409 PaymentAlreadyExists if yes)

3. Simulate payment:
   _charge(order.total_amount, method)
   → returns (SIM-CARD-abc123, True, None)

4. If prior "failed" payment exists: update it in place
   Else: create new Payment record

5. Move order to "paid" via update_status

Result: Payment with status="success", Order with status="paid"
```

---

### Workflow 4: Order Cancellation

**Customer cancels (POST /order/{id}/cancel):**
```
1. Fetch order; check caller is owner or admin/staff
2. update_status(order_id, "cancelled")
   → validate transition: pending→cancelled ✅ or paid→cancelled ✅
   → _restock_items(db, order):
      For each OrderItem:
        SELECT product FOR UPDATE
        StockService.increase(quantity, reason="cancellation", reference="order#N", commit=False)
   → order.status = "cancelled"
   → db.commit()
```

**Admin changes status to cancelled (PATCH /order/{id}/status):**
- Same update_status call, same restock logic.

---

### Workflow 5: Report Data Sync

```
1. Client/startup → POST /report/sync
   Requires admin/staff token

2. SyncService.sync_all(db):
   a. Mint internal service token (sub="report_service", role="admin", exp=5min)
   
   b. sync_users:
      Paginate GET http://user_service:8001/user?page=N&page_size=100
      For each user: upsert UserSnapshot (get by user_id PK → update or insert)
      db.commit() after all pages
   
   c. sync_products:
      Paginate GET http://operation_service:8002/product?active_only=False&page=N
      For each product: upsert ProductSnapshot
      db.commit() after all pages
   
   d. sync_orders:
      Paginate GET http://operation_service:8002/order?page=N
      For each order:
        upsert OrderSnapshot
        clear existing OrderItemSnapshot items (if updating)
        re-add OrderItemSnapshot items
      db.commit() after all pages

3. Return: { users_synced, products_synced, orders_synced }
```

---

## Business Rules Summary

### User Management
- Email must be unique across all active (non-deleted) users
- Passwords stored as bcrypt hashes only; plain text never persisted
- Role transitions: customer ↔ staff ↔ admin (any direction, admin only)
- Soft delete: `deleted_at` + `is_active=False`; deleted users cannot log in
- All user queries exclude deleted users (`deleted_at IS NULL`)
- Only the owner can change their own password; requires old password verification
- Admin or self can update profile; staff cannot update other users' profiles

### Product Management
- Product names must be unique across non-deleted products
- Stock can only be modified through `StockService` (enforced by convention, not DB)
- Every stock change creates an immutable `StockMovement` record
- `deactivate` (DELETE endpoint) sets `is_active=False` only; does not set `deleted_at`
- Deleted products (soft-deleted) are excluded from all queries
- Inactive products cannot be ordered

### Order Management
- An order must have at least one item
- Items for inactive products are rejected at order time
- Stock check and decrement are atomic within a single DB transaction
- Row-level locking (`SELECT FOR UPDATE`) prevents concurrent overselling
- Price and name are snapshotted at order creation time (immune to product updates)
- Status state machine is strictly enforced:
  - `pending` → `paid` or `cancelled`
  - `paid` → `completed` or `cancelled`
  - `cancelled` → terminal (no further transitions)
  - `completed` → terminal (no further transitions)
- Cancellation always triggers stock restoration for all line items

### Payment
- Only `pending` orders can be paid
- Only one successful payment per order (idempotency check)
- Failed payments can be retried (updated in place)
- Payment gateway is currently simulated (always succeeds for amount > 0)

### Reporting
- All reports read exclusively from `report_service_db` (`*_snapshot` tables)
- Snapshot data is eventually consistent with source services
- Revenue calculations include only `paid` and `completed` orders
- Date range defaults to trailing 30 days; validated (`start ≤ end`)
- `low-stock` report uses current snapshot data, not a date range

---

## State Transitions

### Order Status State Machine

```
         ┌─────────────────────┐
         │                     │
   POST /order           POST /order/{id}/cancel
         │                POST /order/{id}/status (→cancelled)
         ▼                     │
      pending ─────────────► cancelled (terminal)
         │
         │ POST /order/{id}/payment
         │ (or PATCH /order/{id}/status → paid)
         ▼
        paid ────────────────► cancelled (terminal)
         │
         │ PATCH /order/{id}/status (→ completed)
         ▼
     completed (terminal)
```

### Payment Status

```
      (new)        failed ───► success (retry)
        │             ▲
        ▼             │
     pending ─────────┤
        │             │
        └─────────────┴──► success
```

---

## Feature Dependencies

| Feature | Depends On |
|---|---|
| Order creation | Products (existence, active, stock), Auth (user_id from JWT) |
| Payment | Orders (status), Payment simulation |
| Order cancellation | Orders (status transition), Products (for restocking) |
| Report generation | SyncService having run at least once |
| SyncService | user_service and operation_service being reachable |
| Stock movement history | Products |
| Role management | User existence |

# Coffee Shop Microservices Platform

A microservice backend for a coffee shop, made up of three independent FastAPI
services that each own their own PostgreSQL database and talk to each other
only through HTTP + a shared, stateless JWT — no service reaches into
another service's database.

| Service | Database | Responsibility |
|---|---|---|
| **user_service** (Auth) | `user_service_db` (`users` table) | Registration, login, password hashing, JWT issuing, role management |
| **operation_service** | `operation_service_db` (`products`, `orders`, `order_items`, `payments`, `stock_movements`) | Menu/product management, stock, order lifecycle, simulated payments |
| **report_service** | `report_service_db` (`users_snapshot`, `products_snapshot`, `orders_snapshot`, `order_items_snapshot`) | Sales, inventory and user analytics — served entirely from its own, locally-synced copy of the data |

---

## 1. How the three services talk to each other

**Auth (JWT), for every request:**
1. `user_service` is the **only** service that issues tokens. `POST /user/login`
   verifies the email/password (bcrypt) and returns a signed JWT containing
   `sub` (user id), `email`, and `role` (`customer` / `staff` / `admin`).
2. `operation_service` and `report_service` never call `user_service` to
   check a token. They verify the JWT signature locally using the **same
   `JWT_SECRET_KEY` / `JWT_ALGORITHM`** configured in all three `.env` files,
   and trust the `role` claim inside it.
3. **The `JWT_SECRET_KEY` in `user_service/app/.env`, `operation_service/.env`
   and `report_service/.env` must be identical**, or tokens issued by the
   auth service will be rejected as invalid everywhere else.

**Data, for report_service only:** report_service owns its own database
(`report_service_db`) with its own `*_snapshot` tables — it does **not**
connect to `user_service_db` or `operation_service_db` directly. Instead, a
`SyncService` pulls data from `user_service`'s and `operation_service`'s
public HTTP APIs (`GET /user`, `GET /product`, `GET /order`) and upserts it
locally. Since those endpoints require a staff/admin token, report_service
mints its own short-lived **internal service-account JWT** (`sub:
"report_service"`, `role: "admin"`) using the same shared secret — this is
the one and only inter-service HTTP call in the whole system, and it is
one-directional (report_service → the other two).

```
Client -> POST /user/login (user_service) -> JWT {sub, email, role}
Client -> GET /product, POST /order, ... (operation_service, Authorization: Bearer <JWT>)
Client -> GET /report/sales-summary (report_service, Authorization: Bearer <JWT>, role must be admin/staff)

report_service -> POST /report/sync (manual, or automatically once at startup)
   -> mints its own internal service JWT
   -> GET /user (user_service), GET /product & GET /order (operation_service)
   -> upserts results into report_service_db's own *_snapshot tables
```

Every service follows the same Clean Architecture layout (`core` /
`dependencies` / `models` / `repository` / `schemas` / `services` / `api`) and
the same response envelope:

```json
{ "success": true, "error_code": null, "message": "...", "data": { ... } }
```

---

## 2. user_service (Auth)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/user` | public | Register (password is bcrypt-hashed before it touches the DB) |
| POST | `/user/login` | public | Login, returns `access_token` (JWT) |
| GET | `/user/me` | any authenticated user | Get my own profile |
| GET | `/user?page=&page_size=` | admin/staff | Paginated list of users |
| GET | `/user/{id}` | self or admin/staff | Get a user |
| PUT | `/user/{id}` | self or admin | Update username/email/is_active |
| PATCH | `/user/{id}/role` | admin | Promote/demote a user's role |
| PATCH | `/user/{id}/password` | self | Change password (requires old password) |
| DELETE | `/user/{id}` | admin | Soft-delete a user |

Security implemented: bcrypt password hashing, JWT issuing/verification,
role-based access control, soft-delete-aware queries, CORS middleware.

## 3. operation_service

**Products** (menu management, paginated listing):

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/product` | admin/staff | Add a product |
| GET | `/product?page=&page_size=&active_only=` | public | Paginated product listing |
| GET | `/product/{id}` | public | Get a product |
| PUT | `/product/{id}` | admin/staff | Update a product |
| POST | `/product/{id}/stock` | admin/staff | Manually adjust stock (restock/adjustment), logged to `stock_movements` |
| DELETE | `/product/{id}` | admin/staff | Deactivate (soft-delete) a product |

**Orders** (core business logic — validates stock, snapshots price, computes total):

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/order` | any authenticated user | Create an order; decrements stock atomically per line item |
| GET | `/order?page=&page_size=&status=` | any authenticated user | Customers see only their own orders; staff/admin see everyone's |
| GET | `/order/{id}` | owner or admin/staff | Get an order |
| PATCH | `/order/{id}/status` | admin/staff | Move order through `pending → paid → completed` or `→ cancelled` (validated transitions; cancelling restocks items) |
| POST | `/order/{id}/cancel` | owner | Convenience endpoint for a customer to cancel their own pending order |

**Payments** (simulated gateway — no real provider is wired up):

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/order/{id}/payment` | owner or admin/staff | Pay for a `pending` order; on success moves the order to `paid` |
| GET | `/order/{id}/payment` | owner or admin/staff | Get payment status for an order |

Stock is never touched directly by any of the above — every increase/decrease
goes through `StockService`, which validates the change and appends an
audit row to `stock_movements` (reason: `restock`, `sale`, `cancellation`,
`adjustment`).

## 4. report_service

report_service owns its own `report_service_db` and serves every report
below entirely from its local `*_snapshot` tables — never from
`user_service_db` / `operation_service_db` directly. `POST /report/sync` (or
the automatic sync at startup) is what keeps those local tables current.

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/report/sync` | admin/staff | Pull the latest users/products/orders from user_service + operation_service into report_service_db |
| GET | `/report/sales-summary` | admin/staff | Total orders, paid/completed orders, cancelled orders, total revenue, average order value |
| GET | `/report/daily-sales` | admin/staff | Revenue and order count grouped by day |
| GET | `/report/top-products?limit=` | admin/staff | Best-selling products by quantity, with revenue |
| GET | `/report/low-stock?threshold=` | admin/staff | Active products at or below a stock threshold |
| GET | `/report/users-summary` | admin/staff | Total/active/inactive users, new signups in range, breakdown by role |

All range-based endpoints accept optional `start_date` / `end_date` (defaults
to the trailing 30 days). If you call any of these right after starting the
service for the very first time and get empty results, run `POST
/report/sync` once manually first — the automatic startup sync only succeeds
if `user_service` and `operation_service` are already up and reachable.

---

## 5. Installation

```bash
git clone <repository-url>
cd coffee_shop
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create three PostgreSQL databases (one per service — or reuse one instance
with three separate DB names, as configured below):

```sql
CREATE DATABASE user_service_db;
CREATE DATABASE operation_service_db;
CREATE DATABASE report_service_db;
```

### Environment files

Each service ships a `.env.example`; copy it to `.env` in the same folder and
fill in real values. **The `JWT_SECRET_KEY` must be identical across all
three `.env` files.**

* `user_service/app/.env` — `DB_*` (own DB) + `JWT_SECRET_KEY`/`JWT_ALGORITHM`/`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
* `operation_service/.env` — `DB_*` (own DB) + the same `JWT_SECRET_KEY`/`JWT_ALGORITHM`
* `report_service/.env` — `DB_*` (its own `report_service_db`) + `USER_SERVICE_BASE_URL`/`OPERATION_SERVICE_BASE_URL` (used only by the sync job) + the same `JWT_SECRET_KEY`/`JWT_ALGORITHM`

### Running each service

Start `user_service` and `operation_service` first, since `report_service`
syncs from them at startup (this is a best-effort sync — it won't crash the
app if they aren't up yet, but reports will be empty until you run `POST
/report/sync` manually or restart report_service once they are).

```bash
# Terminal 1
cd user_service && uvicorn app.main:app --reload --port 8001

# Terminal 2
cd operation_service && uvicorn app.main:app --reload --port 8002

# Terminal 3 (start after the two above)
cd report_service && uvicorn app.main:app --reload --port 8003
```

Swagger UI is available at `/docs` on each port. `test_main.http` files are
included in every service folder (VS Code REST Client / PyCharm HTTP Client
compatible) with a full walk-through: register → login → add product →
create order → pay → sync → check reports.

### Local development note on schema creation

All three services call `Base.metadata.create_all()` on startup for
convenience in local development, each against its own database only — this
is fine for a coursework-scale project but should be replaced with Alembic
migrations (already in `requirements.txt`) before pointing this at a
shared/production database.

---

## 6. Design notes / trade-offs

* **No cross-service network calls for regular auth checks.** operation_service
  and report_service trust the JWT's claims (`id`, `email`, `role`) for every
  normal request instead of calling back to user_service to re-verify the
  user. This is a common, low-latency pattern for stateless JWT auth, at the
  cost of claims going stale until the token expires (e.g. a role change
  won't take effect until the user logs in again).
* **report_service's data is eventually consistent, not live.** It only ever
  sees what the last sync pulled in. `POST /report/sync` is manual/on-demand
  plus a best-effort run at startup — a real deployment would put this
  behind a scheduler (cron, APScheduler, or a message-queue consumer
  reacting to order/payment events) instead of relying on someone to call it.
* **The sync job authenticates like any other client.** report_service mints
  its own internal JWT with the shared secret and calls the exact same public
  `/user`, `/product`, `/order` endpoints a normal admin dashboard would —
  there's no special "internal" API surface to keep in sync separately.
* **Payments are simulated.** `PaymentService._charge()` fakes a gateway call
  and always succeeds for a positive order total — swap it for a real
  provider SDK to go to production.
* **Stock changes are transactional.** Creating an order that fails partway
  through (e.g. the 2nd line item is out of stock) rolls back every stock
  decrement already made for that order, so stock is never left partially
  decremented.
* **report_service's snapshot tables are denormalized on purpose.** They
  only carry the columns needed for reporting (e.g. no password hashes),
  and are entirely disposable/rebuildable by re-running `/report/sync` — the
  real system of record for that data always stays in `user_service_db` /
  `operation_service_db`.

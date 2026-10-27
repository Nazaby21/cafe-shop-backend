# Technical Debt and Recommendations

This document provides a prioritized breakdown of technical debt, architectural anomalies, security risks, and optimization opportunities discovered during the comprehensive static and structural analysis of the Coffee Shop backend.

---

## 1. Critical Issues

### 1.1 Insecure Default Fallback for `JWT_SECRET_KEY`

- **Affected Files:**
  - `user_service/app/core/config.py` (Line 17)
  - `operation_service/app/core/config.py` (Line 17)
  - `report_service/app/core/config.py` (Line 28)
- **Technical Explanation:**
  All three services configure `JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")`. If the environment variable is not explicitly loaded, all three services default to using the plaintext string `"change-me-in-production"`.
- **Potential Impact:**
  Any malicious actor knowing the default key can mint arbitrary administrative JWT tokens (`sub="attacker", role="admin"`) and gain complete administrative access to all three microservices.
- **Dependencies:** None.
- **Suggested Solution:**
  Fail fast on application startup if `JWT_SECRET_KEY` is not provided in production:
  ```python
  JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
  if not JWT_SECRET_KEY:
      raise RuntimeError("JWT_SECRET_KEY environment variable must be set!")
  ```

---

### 1.2 `user_service` `.env` Directory Location Mismatch

- **Affected Files:**
  - `user_service/app/.env`
  - `user_service/app/core/config.py` (Line 4)
- **Technical Explanation:**
  The `.env` file for `user_service` is placed in `user_service/app/.env` rather than `user_service/.env`. In `config.py`, `load_dotenv()` with no arguments searches the current working directory. When starting the service via `cd user_service && uvicorn app.main:app`, `load_dotenv()` inspects `user_service/` and fails to find `app/.env`. All database environment variables (`DB_NAME`, `DB_USER`, `DB_PASSWORD`) resolve to `None`.
- **Potential Impact:**
  Application startup crashes with a database connection error (`postgresql+psycopg2://None:None@None:None/None`) unless manually executed from within the `app/` folder or explicitly given a file path.
- **Dependencies:** `python-dotenv`.
- **Suggested Solution:**
  Move `.env` and `.env.example` up one level to `user_service/.env` (matching `operation_service` and `report_service`), or specify `load_dotenv(Path(__file__).resolve().parent.parent / ".env")`.

---

### 1.3 Absence of Database Schema Migrations (Alembic)

- **Affected Files:**
  - `user_service/app/main.py` (Line 15)
  - `operation_service/app/main.py` (Line 22)
  - `report_service/app/main.py` (Line 24)
- **Technical Explanation:**
  All services invoke `Base.metadata.create_all(bind=engine)` at runtime. Alembic is present in `requirements.txt` (v1.18.4) but has not been initialized (`alembic init` was never run).
- **Potential Impact:**
  `create_all()` only creates non-existent tables; it cannot add columns, alter data types, or modify constraints on existing tables. Schema evolution in production will require manual SQL scripts, leading to drift, data loss risk, and unversioned database states.
- **Dependencies:** SQLAlchemy, Alembic.
- **Suggested Solution:**
  Initialize Alembic independently per service (or a unified migrations runner), generate baseline migrations from the existing models, and remove `create_all()` from `main.py`.

---

## 2. High-Priority Issues

### 2.1 Complete Absence of Automated Testing

- **Affected Files:** Entire project repository (no `tests/` directory).
- **Technical Explanation:**
  There are zero unit tests, integration tests, or API route tests. Verification is entirely reliant on manual execution through `.http` client files.
- **Potential Impact:**
  High risk of regression during feature addition or refactoring. Subtle edge cases (e.g. concurrent race conditions, invalid status transitions) cannot be verified in automated CI/CD pipelines.
- **Dependencies:** None.
- **Suggested Solution:**
  Add `pytest`, `pytest-asyncio`, and `httpx` to `requirements.txt`. Create a `tests/` directory in each service containing unit tests for services and API tests using FastAPI's `TestClient`.

---

### 2.2 Non-Atomic Payment and Order Status Update Transaction

- **Affected Files:**
  - `operation_service/app/services/payment_service.py` (Lines 59-62)
- **Technical Explanation:**
  In `PaymentService.pay_for_order`:
  ```python
  payment = payment_repo.update(db, payment) if existing else payment_repo.create(db, payment)
  # Move the order forward now that payment succeeded.
  self.order_service.update_status(db, order_id, OrderStatus.PAID)
  ```
  `payment_repo.create(db, payment)` executes `db.commit()` inside the repository. Then `order_service.update_status()` executes its own transaction and commits.
- **Potential Impact:**
  If the network or server crashes, or if `order_service.update_status` encounters an unexpected error immediately after `payment_repo.create()`, the payment row is committed with status `SUCCESS`, but the order remains in `PENDING` state!
- **Dependencies:** SQLAlchemy Session.
- **Suggested Solution:**
  Manage transactions at the service boundary. Have repository methods accept `commit: bool = True` (or use a Unit of Work / transaction manager) so payment creation and order status update commit in a single atomic transaction.

---

### 2.3 Unhandled Validation Error Response Format

- **Affected Files:**
  - `user_service/app/core/exception_handler.py`
  - `operation_service/app/core/exception_handler.py`
  - `report_service/app/core/exception_handler.py`
- **Technical Explanation:**
  FastAPI registers default handlers for `RequestValidationError` (Pydantic validation failures) and Starlette `HTTPException`. The services only register a custom handler for `ApplicationError`.
- **Potential Impact:**
  Clients receive inconsistent response formats:
  - Business errors: `{"success": false, "error_code": "err_404", "message": "...", "data": null}`
  - Pydantic schema validation errors: `{"detail": [{"loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error"}]}`
- **Dependencies:** FastAPI, Starlette.
- **Suggested Solution:**
  Add an exception handler for `RequestValidationError` that translates validation errors into the standard `ApiResponse` envelope with `error_code="err_422_validation"`.

---

### 2.4 User Profile Update Allows Modification of `is_active`

- **Affected Files:**
  - `user_service/app/schemas/user_schema.py` (Lines 27-30)
  - `user_service/app/api/user_route.py` (Lines 80-92)
- **Technical Explanation:**
  `UpdateUserRequest` includes `is_active: bool = True`. When a customer updates their own profile via `PUT /user/{user_id}`, `UserService.update_user` sets `user.is_active = request.is_active`.
- **Potential Impact:**
  A customer could inadvertently deactivate their own account (preventing subsequent logins) or theoretically manipulate account activation state.
- **Dependencies:** Pydantic schemas.
- **Suggested Solution:**
  Separate customer profile updates from administrative account management. `UpdateUserRequest` (for users) should only contain `username` and `email`. A separate administrative endpoint/schema should manage `is_active`.

---

## 3. Medium-Priority Improvements

### 3.1 Code Duplication Across Microservices

- **Affected Files:**
  - `app/schemas/api_response.py` (Identical in all 3 services)
  - `app/core/exception_handler.py` (Identical in all 3 services)
  - `app/core/database.py` (Identical structure in all 3 services)
  - `app/dependencies/db.py` (Identical in all 3 services)
- **Technical Explanation:**
  Common utility classes, response envelopes (`ApiResponse`, `PageMeta`, `PaginatedData`), database initialization logic, and exception handlers are duplicated verbatim across all three services.
- **Potential Impact:**
  Bug fixes or enhancements to the response envelope or error handling must be copied manually to three separate locations, increasing maintenance overhead.
- **Suggested Solution:**
  Extract shared schemas, core utilities, and base models into an internal shared package (e.g. `coffee_shop_common`) installable via `pip install -e ./common`.

---

### 3.2 O(N) Sequential Querying in Report Service Sync

- **Affected Files:**
  - `report_service/app/services/sync_service.py` (Lines 48-140)
- **Technical Explanation:**
  `SyncService` iterates through paginated JSON payloads and executes an individual `db.get()` query for every user, product, and order item.
- **Potential Impact:**
  For 10,000 orders and items, the sync operation issues tens of thousands of individual database roundtrips, resulting in high latency, connection pool saturation, and potential timeouts.
- **Suggested Solution:**
  Utilize PostgreSQL bulk upserts:
  ```python
  from sqlalchemy.dialects.postgresql import insert
  stmt = insert(ProductSnapshot).values([...])
  stmt = stmt.on_conflict_do_update(
      index_elements=['product_id'],
      set_={...}
  )
  db.execute(stmt)
  ```

---

### 3.3 Missing Logging and Telemetry

- **Affected Files:**
  - `user_service/` (0 log statements)
  - `operation_service/` (0 log statements)
- **Technical Explanation:**
  Neither `user_service` nor `operation_service` configures or calls Python's `logging` module.
- **Potential Impact:**
  Zero visibility into system operations, failed login attempts, unauthorized access attempts, or transaction rollbacks in production environments.
- **Suggested Solution:**
  Implement standardized structured logging (e.g. using `structlog` or Python's standard `logging.config.dictConfig`) with correlation IDs attached via FastAPI middleware.

---

### 3.4 Dead / Stray Stub Files

- **Affected Files:**
  - `operation_service/main.py`
  - `report_service/main.py`
  - `operation_service/app/repository/stock_repository.py` (`get_movements_for_product`)
- **Technical Explanation:**
  - Root `main.py` files in `operation_service` and `report_service` contain boilerplate FastAPI "Hello World" code left over from project initialization. The actual applications reside in `app/main.py`.
  - `get_movements_for_product` is implemented in `stock_repository.py` but is never referenced by any service or API route.
- **Potential Impact:**
  Developer confusion regarding application entry points and dead code clutter.
- **Suggested Solution:**
  Safely remove root `main.py` files (or redirect them to `app/main.py`) and expose an audit endpoint `GET /product/{id}/movements` (admin/staff) to utilize the existing repository query.

---

## 4. Low-Priority Improvements

### 4.1 Timezone-Naive Datetimes

- **Affected Files:** All models using `default=datetime.now`.
- **Technical Explanation:**
  `datetime.now` (without `timezone.utc`) produces naive timestamps based on the server's local operating system clock. In contrast, JWT tokens in `security.py` use `datetime.now(timezone.utc)`.
- **Potential Impact:**
  Timestamp comparisons between token expiry and database timestamps or distributed database servers across different time zones can yield inaccurate time calculations.
- **Suggested Solution:**
  Use timezone-aware datetimes across all models:
  ```python
  from datetime import datetime, timezone
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
  ```

---

### 4.2 Missing Database-Level CHECK Constraints

- **Affected Files:**
  - `operation_service/app/models/product.py` (`price`, `stock_quantity`)
  - `operation_service/app/models/order.py` (`quantity`, `subtotal`)
- **Technical Explanation:**
  Constraints like `stock_quantity >= 0` and `price > 0` are currently enforced only in application code and Pydantic schemas, not at the database table level via `CheckConstraint`.
- **Potential Impact:**
  A direct database query, script, or bug in application logic could lead to negative stock or zero-dollar pricing.
- **Suggested Solution:**
  Add SQLAlchemy `CheckConstraint("stock_quantity >= 0", name="chk_stock_non_negative")`.

---

## 5. Optional Future Enhancements

1. **API Gateway / Unified Entrypoint:** Implement NGINX, Traefik, or Kong in front of all three services so client applications interact with a single host and port.
2. **Event-Driven Architecture (Message Broker):** Replace HTTP polling sync in `report_service` with an event-driven mechanism using RabbitMQ or Kafka (e.g. `order.created`, `order.paid` events consumed by `report_service`).
3. **Token Blacklisting and Refresh Tokens:** Implement refresh tokens stored in Redis to support immediate revocation when users are deactivated or change roles.
4. **Real Payment Gateway Integration:** Replace simulated `PaymentService._charge()` with Stripe or PayPal SDKs.

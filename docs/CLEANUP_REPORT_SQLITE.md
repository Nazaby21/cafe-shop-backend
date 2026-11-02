# SQLite Cleanup Report (`docs/CLEANUP_REPORT_SQLITE.md`)

## 1. Summary of SQLite Code and Config Removed

The following SQLite configurations, workarounds, and database files have been audited and removed from the codebase:

### 1.1 Application Configuration & Database Drivers
- `user_service/app/core/database.py`:
  - Removed `check_same_thread = False` legacy SQLite hook.
  - Configured PostgreSQL `create_engine` directly with `pool_pre_ping=True`.
- `operation_service/app/core/database.py`:
  - Removed `check_same_thread = False` legacy SQLite hook.
  - Configured PostgreSQL `create_engine` directly with `pool_pre_ping=True`.
- `report_service/app/core/database.py`:
  - Removed `check_same_thread = False` legacy SQLite hook.
  - Configured PostgreSQL `create_engine` directly with `pool_pre_ping=True`.
- `user_service/app/core/config.py`:
  - Added strict guard: `DATABASE_URL.startswith("sqlite")` raises a `ValueError` prohibiting SQLite.
  - Enforced `env_file` auto-discovery targeting the service root `.env`.
- `operation_service/app/core/config.py`:
  - Added strict guard: `DATABASE_URL.startswith("sqlite")` raises a `ValueError` prohibiting SQLite.
  - Added `BAKONG_MODE: Literal["mock", "sandbox"] = "mock"` setting.
- `report_service/app/core/config.py`:
  - Added strict guard: `DATABASE_URL.startswith("sqlite")` raises a `ValueError` prohibiting SQLite.

### 1.2 Test Suites & Pytest Configuration
- `user_service/tests/conftest.py`:
  - Removed in-memory SQLite (`sqlite:///:memory:`, `StaticPool`, and `check_same_thread`).
  - Configured test engine to target PostgreSQL test database (`user_service_test_db`).
  - Configured session-scoped `drop_all` / `create_all` table lifecycle and per-test `create_savepoint` transaction rollback isolation.
- `operation_service/tests/conftest.py`:
  - Removed in-memory SQLite (`sqlite:///:memory:`, `StaticPool`, and `check_same_thread`).
  - Configured test engine to target PostgreSQL test database (`operation_service_test_db`).
  - Configured session-scoped `drop_all` / `create_all` table lifecycle and per-test `create_savepoint` transaction rollback isolation.
- `report_service/tests/conftest.py`:
  - Removed in-memory SQLite (`sqlite:///:memory:`, `StaticPool`, and `check_same_thread`).
  - Configured test engine to target PostgreSQL test database (`report_service_test_db`).
  - Configured session-scoped `drop_all` / `create_all` table lifecycle and per-test `create_savepoint` transaction rollback isolation.

### 1.3 Integration Test Runners
- `scripts/run_integration_check.py`:
  - Removed temporary SQLite disk database creation (`user_itest.db`, `operation_itest.db`, `report_itest.db`).
  - Updated all 4 stages (user_service, operation_service, report_service, cascade verification) to execute against PostgreSQL test databases (`user_service_test_db`, `operation_service_test_db`, `report_service_test_db`).
- `tests/test_cross_service_integration.py`:
  - Updated pytest wrapper to resolve module paths and execute the PostgreSQL end-to-end check.

---

## 2. Legacy SQLite Binary Files Audit

Three physical SQLite database files were discovered in the repository root:
- `coffee_shop/user_service.db` (40 KB)
- `coffee_shop/operation_service.db` (48 KB)
- `coffee_shop/report_service.db` (40 KB)

### Row Count & Data Verification
```python
# Inspected via sqlite3 on 2026-11-02:
user_service.db: users = 0 rows
operation_service.db: categories = 0, products = 0, orders = 0, payments = 0, stock_movements = 0
report_service.db: users_snapshot = 0, products_snapshot = 0, orders_snapshot = 0, order_items_snapshot = 0
```
- **Data Migration Requirement**: None. Because all tables contained 0 rows, no data migration script was needed. The canonical schema is defined in SQLAlchemy models and Alembic migrations.
- **Safety Status**: Marked **SAFE TO DELETE** in a dedicated cleanup commit.

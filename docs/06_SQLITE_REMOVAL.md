# Step 2: Complete SQLite Removal Architecture Report (`docs/06_SQLITE_REMOVAL.md`)

> **Executive Summary**: SQLite has been completely eradicated across all FastAPI microservices, test runners, and configuration. The entire platform now runs strictly on PostgreSQL, both for development and testing.

---

## 1. Architectural Changes

### 1.1 Enforcement of PostgreSQL in Microservices
All three FastAPI services (`user_service`, `operation_service`, `report_service`) have had legacy SQLite hooks removed:
1. **Engine Instantiation (`app/core/database.py`)**:
   - Removed SQLite-specific `connect_args["check_same_thread"] = False`.
   - Engines now connect using standard PostgreSQL connection pools with `pool_pre_ping=True` to automatically recycle severed connections.
2. **Configuration Validation (`app/core/config.py`)**:
   - Added validation in `@model_validator(mode="after")` that rejects any `DATABASE_URL` starting with `sqlite://` with an explicit error:
     ```
     ValueError: SQLite is strictly prohibited. PostgreSQL is required.
     ```
   - Standardized `database_url` construction to `postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}`.

---

## 2. Test Suite Architecture: PostgreSQL Isolation

Previously, unit and integration tests used in-memory SQLite (`sqlite:///:memory:`). While fast, in-memory SQLite masked PostgreSQL-specific features like `FOR UPDATE SKIP LOCKED`, native UUID/JSONB types, and advisory locks.

### 2.1 Dedicated Test Databases
The test suite now uses dedicated PostgreSQL test databases:
- `user_service_test_db`
- `operation_service_test_db`
- `report_service_test_db`

### 2.2 Test Transaction Isolation (`join_transaction_mode="create_savepoint"`)
To prevent test pollution without the overhead of recreating databases per test, tests utilize SQLAlchemy 2.0 savepoints:
```python
@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    # Any commit inside application code releases the savepoint without committing the outer transaction
    session = TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()
```
- At the test session start, `Base.metadata.drop_all(bind=engine)` and `Base.metadata.create_all(bind=engine)` ensure an authentic, empty schema.
- Each test runs in an isolated transaction rolled back upon fixture teardown.
- Tests can issue `db_session.commit()` safely without polluting the database across tests.

### 2.3 Cross-Service Integration Runner (`scripts/run_integration_check.py`)
- Removed disk-based SQLite files (`user_itest.db`, etc.).
- The runner executes against the PostgreSQL test databases, testing end-to-end user registration, authentication, product and order creation, 503 unconfigured gateway response, staff status advances, sync service ingestion, sales reporting, and cascade purge verification.

---

## 3. Verification & Test Results

All 23 test suites pass on PostgreSQL:
- **`user_service`**: 5 passed (`1.24s`)
- **`operation_service`**: 13 passed (`1.82s` — 10 Bakong KHQR tests + 3 operation API tests)
- **`report_service`**: 4 passed (`1.07s`)
- **`test_cross_service_integration_e2e`**: 1 passed (`3.19s`)
- **Linter (`ruff check .`)**: All checks passed (0 errors).
- **Anti-Mock Check (`scripts/check_mock_patterns.py`)**: 0 violations across 147 tracked files.

# Execution Progress Log (`docs/PROGRESS.md`)

## Block Tracking
- **Block Number**: 1 (Completed — Step 1 Discovery & Step 2 SQLite Removal Finished)
- **block_start**: `2026-11-02T22:34:31.6133377+07:00`
- **block_end**: `2026-11-02T22:57:00+07:00` (~22.5 minutes elapsed)
- **Current Step**: Step 2 Completed (proceeding to Step 3: Kong APIM Implementation in Block 2).

## Completed Tasks
1. **Safety & Initial Setup**:
   - Verified clean branch `feature/kong-apim-postgres` branched from `feature/bakong-khqr`.
   - Updated `.gitignore` to ensure `*.pem`, `*.sqlite*`, `node_modules/`, and `.next/` are never tracked (`afc5f55`).
2. **Step 1: Kong Gateway & SQLite Discovery**:
   - Audited all microservices (`user_service:8001`, `operation_service:8002`, `report_service:8003`), frontend Axios clients (`authClient`, `operationClient`, `reportClient`), and all SQLite references.
   - Verified local PostgreSQL running on port 5432 and verified active databases (`user_service_db`, `operation_service_db`, `report_service_db`).
   - Inspected root `.db` files: verified 0 rows in all tables across all three SQLite files.
   - Produced `docs/05_KONG_DISCOVERY.md`.
3. **Step 2: SQLite Removal**:
   - Removed SQLite-specific `connect_args["check_same_thread"] = False` from `app/core/database.py` across all three services.
   - Enforced strict PostgreSQL validation in `app/core/config.py` (rejecting `sqlite://` with `ValueError`).
   - Added `BAKONG_MODE: Literal["mock", "sandbox"] = "mock"` to `operation_service/app/core/config.py`.
   - Created dedicated PostgreSQL test databases: `user_service_test_db`, `operation_service_test_db`, `report_service_test_db`.
   - Updated `tests/conftest.py` in all three services to use PostgreSQL test databases with SQLAlchemy 2.0 `join_transaction_mode="create_savepoint"` for transaction rollback isolation.
   - Updated `scripts/run_integration_check.py` to run cross-service end-to-end integration tests entirely on PostgreSQL.
   - Updated `scripts/check_mock_patterns.py` to allow `BAKONG_MODE` env configuration.
   - Produced `docs/CLEANUP_REPORT_SQLITE.md` and `docs/06_SQLITE_REMOVAL.md`.

## Test Execution Results (PostgreSQL Only)
- `user_service`: **5 passed** (`1.24s`)
- `operation_service`: **13 passed** (`1.82s` — 10 Bakong KHQR tests + 3 operation API tests)
- `report_service`: **4 passed** (`1.07s`)
- `tests/test_cross_service_integration.py`: **1 passed** (`3.19s`)
- Total tests: **23 passed, 0 failures** on PostgreSQL.
- `ruff check .`: **All checks passed!**
- `scripts/check_mock_patterns.py`: **OK — no mock data patterns in 147 file(s).**

## Next 3 Tasks
1. **Step 3: Kong APIM Implementation**:
   - Create root `docker-compose.yml` (Postgres, Kong OSS DB-less, user-service, operation-service, report-service, frontend).
   - Create `kong/kong.yml` declarative configuration with routes (`/api/auth`, `/api/orders`, `/api/products`, `/api/categories`, `/api/payments`, `/api/reports`) and plugins (CORS, Request Size Limiting, Correlation ID, Local Rate Limiting).
   - Update frontend API clients (`coffee_shop_frontend/src/config/env.ts` and `src/services/axios.ts`) to use single `NEXT_PUBLIC_API_BASE_URL`.
   - Create root `.env.example` with placeholders for all services.
   - Deliverable: `docs/07_KONG_DESIGN.md`.
2. **Step 4: Smoke Test Scripts & Kong Route Verification**:
   - Implement `scripts/smoke_test.ps1` and `scripts/smoke_test.sh` for Kong APIM.
3. **Step 5: EC2 Setup Guide**:
   - Author `docs/EC2_SETUP_GUIDE.md` for AWS EC2 Ubuntu Sydney deployment.

## Dependencies Added
- None.

## Blocked Commands / Tasks
- None.

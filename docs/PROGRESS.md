# Execution Progress Log (`docs/PROGRESS.md`)

## Block Tracking
- **Block Number**: 2 (Completed — Step 3 Kong APIM & Step 4 Smoke Test Verification Finished)
- **block_start**: `2026-11-02T22:59:34.2922900+07:00`
- **block_end**: `2026-11-02T23:30:00+07:00` (~30.5 minutes elapsed)
- **Current Step**: Step 4 Completed (proceeding to Step 5: EC2 Setup Guide in Block 3).

## Completed Tasks
1. **Block 1 (`dd3bcb2`)**:
   - Step 1 Discovery completed (`docs/05_KONG_DISCOVERY.md`).
   - Step 2 Complete SQLite removal: updated `app/core/database.py`, `app/core/config.py`, created `user_service_test_db`, `operation_service_test_db`, `report_service_test_db`, updated `conftest.py` with `join_transaction_mode="create_savepoint"`, updated `scripts/run_integration_check.py`, produced `docs/CLEANUP_REPORT_SQLITE.md` and `docs/06_SQLITE_REMOVAL.md`.
2. **Block 2 (Kong APIM Implementation, Mock Bakong Switch, Frontend URL Consolidation, Smoke Tests)**:
   - **Kong Declarative Gateway Configuration**: Created `coffee_shop/kong/kong.yml` in DB-less mode (`_format_version: "3.0"`) with upstream routes for `user-service` (`/api/auth`), `operation-service` (`/api/orders`, `/api/products`, `/api/categories`, `/api/payments`), `report-service` (`/api/reports`), and `/health`.
   - **Kong Open-Source Plugins**: Configured CORS (credentials: true), Correlation ID (`X-Request-ID`), Request Size Limiting (10MB), and Rate Limiting (`policy: local`, 100/min global, 10/min on login, 20/min on payments).
   - **Docker Infrastructure**: Created root `docker-compose.yml` orchestrating `postgres` (with `init-databases.sh`), `kong` (`kong:3.9-alpine` in DB-less mode), `user-service`, `operation-service`, `report-service`, and `frontend`. Configured host port isolation (only Kong `8000` and frontend `3000` exposed; Admin API bound strictly to `127.0.0.1:8001`).
   - **Backend Dockerfiles**: Created Dockerfiles for `user_service`, `operation_service`, `report_service`, and `coffee_shop_frontend`.
   - **Mock Bakong Switch**: Extended `bakong_khqr.py` with `BakongClientInterface`, `RealBakongClient`, and `MockBakongClient`, switchable via `BAKONG_MODE=mock|sandbox` (default `mock`). Added testing settlement endpoint `POST /payment/mock-pay/{md5}`.
   - **Health Checks**: Added `GET /health` to all three backend microservices verifying active PostgreSQL database connectivity.
   - **Frontend Migration**: Consolidated frontend API clients in `coffee_shop_frontend/src/config/env.ts` and `src/services/axios.ts` to single `NEXT_PUBLIC_API_BASE_URL`. Updated all 7 feature API endpoints (`/api/auth/...`, `/api/orders/...`, `/api/products/...`, `/api/categories/...`, `/api/reports/...`, `/api/payments/...`).
   - **Smoke Test Suites**: Authored `coffee_shop/scripts/smoke_test.ps1` (PowerShell) and `coffee_shop/scripts/smoke_test.sh` (Bash).
   - **Deliverable**: Authored `docs/07_KONG_DESIGN.md` with complete architecture report and Mermaid sequence diagram.

## Test Execution Results (PostgreSQL Only)
- `user_service`: **5 passed** (`1.25s`)
- `operation_service`: **14 passed** (`1.99s` — 11 Bakong KHQR & mock payment tests + 3 operation API tests)
- `report_service`: **4 passed** (`1.00s`)
- `tests/test_cross_service_integration.py`: **1 passed** (`3.09s`)
- Total tests: **24 passed, 0 failures** on PostgreSQL.
- `ruff check .`: **All checks passed!**
- `scripts/check_mock_patterns.py`: **OK — no mock data patterns in 150 file(s).**
- `coffee_shop_frontend` (`npm run type-check`): **0 errors.**

## Next 3 Tasks
1. **Step 5: EC2 Setup & Operations Guide**:
   - Produce `docs/EC2_SETUP_GUIDE.md` covering AWS EC2 Ubuntu Sydney setup, `icacls` Windows .pem fix, SSH tunnel, Docker Engine & Compose install, migrations, and mock payment test.
2. **Step 6: Final Summary & Documentation Sync**:
   - Produce `docs/FINAL_SUMMARY_KONG.md` summarizing the complete transition.
3. **Legacy SQLite Deletion**:
   - Perform safe deletion of empty SQLite database files in a separate commit `cleanup: remove legacy sqlite database files`.

## Dependencies Added
- None.

## Blocked Commands / Tasks
- None.

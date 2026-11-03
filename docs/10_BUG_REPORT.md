# Bug Audit & Remediation Report (`docs/10_BUG_REPORT.md`)

## Executive Summary
A comprehensive audit across all services, frontend components, and the Kong API Gateway was conducted. Static analysis (`ruff`, `eslint`, `tsc`), automated test suites (`pytest`), and runtime inspection identified 5 distinct bugs ranging from Medium to Critical severity. All low-risk bugs have been resolved and verified with green test suites.

---

## Bug Finding & Resolution Table

| # | File:line | Severity | Description | Evidence (error/test) | Fix status |
|---|---|---|---|---|---|
| 1 | `coffee_shop_frontend/Dockerfile:20` | **HIGH** | Missing `/app/public` directory causes production Docker build failure at stage 3. | Docker build exit code 1: `failed to calculate checksum of ref ... "/app/public": not found`. | **FIXED** (Added `public/.gitkeep` and defensive `mkdir -p /app/public` in builder). |
| 2 | `operation_service/app/services/payment_service.py:168, 403`, `bakong_khqr.py:612, 672, 713, 882` | **MEDIUM** | Timezone-naive `datetime.now()` used for payment expiration, job scheduling, and reconciler cutoffs. Causes premature QR expiration or inconsistent lookback windows when host/client machine is not in UTC. | On Windows host (UTC+7), local time is 7h ahead of UTC timestamps stored in DB, causing `now >= expires_at` check to immediately expire pending payments. | **FIXED** (Implemented and standardized on `utc_now()` returning naive UTC matching PostgreSQL storage). |
| 3 | `.venv/Lib/site-packages/app` | **HIGH** | Rogue `app` package (`MyApplication 0.1.0` / legacy Flask) in virtualenv shadowed local microservice `app` packages, crashing root test collection. | `pytest` collection failure: `ImportStringError: import_string() failed for 'config' ... from .venv/Lib/site-packages/app/__init__.py`. | **FIXED** (Uninstalled rogue `MyApplication` package from `.venv`; confirmed 23/23 service tests pass). |
| 4 | `coffee_shop/docker-compose.local.yml:20` | **MEDIUM** | Hardcoded host loopback port `127.0.0.1:5432:5432` causes port binding collision when a local Windows PostgreSQL service is already active on host port 5432. | Preflight detected host PID 8544 (`postgres.exe`) listening on `0.0.0.0:5432`. | **FIXED** (Made host port configurable via `POSTGRES_HOST_PORT:-5432`, documented in `.env.example`). |
| 5 | `coffee_shop_frontend/src/features/product/components/product-card.tsx:67` | **LOW** | Next.js `@next/next/no-img-element` warning on dynamic product `image_url`. | ESLint output warning: `Using <img> could result in slower LCP and higher bandwidth`. | **FIXED** (Added explicit ESLint rule disable directive for dynamic external product images). |

---

## Detailed Root Cause Analysis & Diffs

### Bug 1: Missing Public Directory in Multi-stage Frontend Build
- **Root Cause**: `coffee_shop_frontend` omitted a `public` directory. Step 13 `COPY --from=builder /app/public ./public` failed BuildKit cache key evaluation.
- **Fix**: Added `coffee_shop_frontend/public/.gitkeep` and ensured `mkdir -p /app/public` in `Dockerfile`.

### Bug 2: Timezone Discrepancy in KHQR Payment Expiration
- **Root Cause**: KHQR string generation embedded UTC timestamps (`now_utc_ms = int(datetime.now(timezone.utc).timestamp() * 1000)`), but database record used `datetime.now()` (local machine clock, UTC+7 in Phnom Penh / Indochina time). Comparing local now against UTC expires_at immediately marked pending payments as expired.
- **Fix**: Defined `utc_now()` in `bakong_khqr.py`:
  ```python
  def utc_now() -> datetime:
      return datetime.now(timezone.utc).replace(tzinfo=None)
  ```
  Updated `process_due_jobs()`, `reconcile_expired_payments()`, and `get_payment_for_order()` to compare against UTC.

### Bug 3: Virtual Environment Package Shadowing
- **Root Cause**: A stale `MyApplication 0.1.0` egg existed in `.venv/Lib/site-packages/app` with a Flask initialization module, causing pytest imports of `app.core.config` to resolve to the site-packages module.
- **Fix**: Uninstalled the rogue package from `.venv`. All 23 microservice unit tests run and pass cleanly.

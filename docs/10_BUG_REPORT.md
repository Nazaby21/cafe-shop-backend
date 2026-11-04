# Bug Audit & Remediation Report (`docs/10_BUG_REPORT.md`)

## Executive Summary
A comprehensive audit across all services, frontend components, and the Kong API Gateway was conducted. Static analysis (`ruff`, `eslint`, `tsc`), automated test suites (`pytest`), and runtime inspection identified 8 distinct bugs ranging from Low to Critical severity. All bugs have been resolved and verified with green test suites and 100% smoke test pass rate (16/16 tests).

---

## Bug Finding & Resolution Table

| # | File:line | Severity | Description | Evidence (error/test) | Fix status |
|---|---|---|---|---|---|
| 1 | `coffee_shop_frontend/Dockerfile:20` | **HIGH** | Missing `/app/public` directory causes production Docker build failure at stage 3. | Docker build exit code 1: `failed to calculate checksum of ref ... "/app/public": not found`. | **FIXED** (Added `public/.gitkeep` and defensive `mkdir -p /app/public` in builder). |
| 2 | `operation_service/app/services/payment_service.py:168, 403`, `bakong_khqr.py:612, 672, 713, 882` | **MEDIUM** | Timezone-naive `datetime.now()` used for payment expiration, job scheduling, and reconciler cutoffs. Causes premature QR expiration or inconsistent lookback windows when host/client machine is not in UTC. | On Windows host (UTC+7), local time is 7h ahead of UTC timestamps stored in DB, causing `now >= expires_at` check to immediately expire pending payments. | **FIXED** (Implemented and standardized on `utc_now()` returning naive UTC matching PostgreSQL storage). |
| 3 | `.venv/Lib/site-packages/app` | **HIGH** | Rogue `app` package (`MyApplication 0.1.0` / legacy Flask) in virtualenv shadowed local microservice `app` packages, crashing root test collection. | `pytest` collection failure: `ImportStringError: import_string() failed for 'config' ... from .venv/Lib/site-packages/app/__init__.py`. | **FIXED** (Uninstalled rogue `MyApplication` package from `.venv`; confirmed 23/23 service tests pass). |
| 4 | `coffee_shop/docker-compose.local.yml:20` | **MEDIUM** | Hardcoded host loopback port `127.0.0.1:5432:5432` causes port binding collision when a local Windows PostgreSQL service is already active on host port 5432. | Preflight detected host PID 8544 (`postgres.exe`) listening on `0.0.0.0:5432`. | **FIXED** (Made host port configurable via `POSTGRES_HOST_PORT:-5432`, documented in `.env.example`). |
| 5 | `coffee_shop_frontend/src/features/product/components/product-card.tsx:67` | **LOW** | Next.js `@next/next/no-img-element` warning on dynamic product `image_url`. | ESLint output warning: `Using <img> could result in slower LCP and higher bandwidth`. | **FIXED** (Added explicit ESLint rule disable directive for dynamic external product images). |
| 6 | `coffee_shop/docker-compose*.yml` | **HIGH** | Kong Admin API container listen address `127.0.0.1:8001` prevented Docker host-port forwarding from reaching Kong inside container. | `smoke.ps1` Kong Admin check failed: `The underlying connection was closed: The connection was closed unexpectedly.` | **FIXED** (Changed container listen to `0.0.0.0:8001` while strictly binding host port to `127.0.0.1:8001:8001`). |
| 7 | `coffee_shop/scripts/smoke.ps1:263, 281, 299` | **MEDIUM** | PowerShell string interpolation bug: `$md5_1?status=paid` treated `$md5_1?status` as variable name, evaluating to empty string and sending request as `mock-pay/%3Dpaid`. | `smoke.ps1` Flow 1-3 failures: `Mock-pay status was simulated; expected paid` due to malformed query string. | **FIXED** (Wrapped variable in braces: `${md5_1}?status=paid`). |
| 8 | `coffee_shop/scripts/smoke.ps1:79, 179, 219` | **LOW** | Windows PowerShell 5.1 `Invoke-WebRequest` hangs indefinitely on HTTP `OPTIONS` response when `-UseBasicParsing` is omitted. | Smoke test runner hung on section 4 (CORS Preflight). | **FIXED** (Added `-UseBasicParsing` across all `Invoke-WebRequest` invocations). |

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

### Bug 4: Host PostgreSQL Port Collision
- **Root Cause**: `docker-compose.local.yml` hardcoded host port binding `127.0.0.1:5432:5432`. On developer workstations running a local PostgreSQL instance (PID 8544 `postgres.exe` in Windows), compose fails to bind the port.
- **Fix**: Replaced hardcoded mapping with `127.0.0.1:${POSTGRES_HOST_PORT:-5432}:5432`.

### Bug 5: Next.js Missing ESLint Rule Override on Image
- **Root Cause**: `product-card.tsx` used standard `<img>` tag for user-uploaded product thumbnails, triggering Next.js lint failure.
- **Fix**: Added explicit ESLint disable comment `// eslint-disable-next-line @next/next/no-img-element` preserving clean CI/CD lint pass.

### Bug 6: Kong Admin API Listen Address Container Isolation
- **Root Cause**: `KONG_ADMIN_LISTEN: 127.0.0.1:8001` restricted Kong Admin to container loopback only. When Docker forwards host connections from `127.0.0.1:8001` across the bridge network to the container's `eth0` interface, Kong dropped the connection (`connection closed unexpectedly`).
- **Fix**: Changed `KONG_ADMIN_LISTEN` to `0.0.0.0:8001` inside the container, while preserving strict host loopback isolation in Compose ports (`127.0.0.1:8001:8001`).

### Bug 7: PowerShell Variable Parsing in URL Query String
- **Root Cause**: In PowerShell, `?` is valid in variable names (`$?`). Writing `$md5_1?status=paid` inside double quotes evaluated `$md5_1?status` as an undefined variable (empty string), producing an HTTP request to `.../mock-pay/%3Dpaid`.
- **Fix**: Wrapped the variable name in curly braces: `${md5_1}?status=paid`.

### Bug 8: PowerShell 5.1 DOM Parser Hang on Headless OPTIONS Requests
- **Root Cause**: `Invoke-WebRequest` in Windows PowerShell 5.1 instantiates an Internet Explorer COM DOM parser by default. On headless servers or Windows dev boxes with uninitialized IE, requests returning empty bodies (such as HTTP `OPTIONS`) hang indefinitely.
- **Fix**: Added `-UseBasicParsing` to all `Invoke-WebRequest` calls in `scripts/smoke.ps1`.

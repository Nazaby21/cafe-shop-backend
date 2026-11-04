# Execution Progress Log (`docs/PROGRESS.md`)

## Project Folder Discovery & Scope Identification
As required by the project safety guidelines, directory scan of `D:\Study\Year-4\Python` identified the following folders:
- `coffee_shop/`: **IN SCOPE** - Core Kong APIM / Bakong KHQR backend stack (`user_service`, `operation_service`, `report_service`, `kong`, `postgres`, `libs`, `scripts`, `docs`). This folder contains the `.git` repository and primary compose configurations.
- `coffee_shop_frontend/`: **IN SCOPE** - Next.js 15 client frontend referenced by compose files (`context: ../coffee_shop_frontend`).
- `docs/`: **IN SCOPE** - Central project documentation and reports.
- `APIM-setup/`: **OUT OF SCOPE** - Unrelated/standalone APIM directory. Will NOT be modified.
- `venv/`: **OUT OF SCOPE** - Host virtual environment. Will NOT be modified.
- `.idea/`: **OUT OF SCOPE** - JetBrains IDE configuration. Will NOT be modified.
- `.ruff_cache/`: **OUT OF SCOPE** - Local tool cache.

### Git Repository Location
- Root check: `git rev-parse --show-toplevel` returned error (`fatal: not a git repository`).
- Git repository location: `D:\Study\Year-4\Python\coffee_shop`.
- Active branch: `fix/cleanup-and-docker-build` (branched from `feature/kong-local-docker` after backup commit `907501a`). All git commands are strictly executed within this repository.

---

## Block Tracking & Step Execution Status
- **Current Step**: STEP 5 COMPLETED (ALL STEPS COMPLETED)
- **Step 0 Completed**: `2026-11-03T19:33:00+07:00`
- **Step 1 Completed**: `2026-11-04T01:41:00+07:00`
- **Step 2 Completed**: `2026-11-04T01:50:00+07:00`
- **Step 3 Completed**: `2026-11-04T02:00:00+07:00`
- **Step 4 Completed**: `2026-11-04T02:05:00+07:00`
- **Step 5 Completed**: `2026-11-04T07:40:00+07:00`
- **Output Artifacts**: 
  - `docs/09_DOCKER_BUILD_REPORT.md`
  - `docs/build-logs/*.log`
  - `docs/10_BUG_REPORT.md`
  - `docs/CLEANUP_REPORT.md`
  - `docs/LOCAL_DOCKER_GUIDE.md`
  - `docs/PROGRESS.md`
  - `docs/OPEN_QUESTIONS.md`
  - `docs/FINAL_SUMMARY_FIXES.md`

### Step 5 Final Verification Results
- **Clean Docker Build**: Both `docker-compose.local.yml` and `docker-compose.yml` build cleanly with 0 errors.
- **Compose Stack Health**: All 6 containers (`frontend`, `kong`, `postgres`, `user-service`, `operation-service`, `report-service`) brought up and verified `healthy`.
- **Smoke Test Suite (`scripts/smoke.ps1`)**:
  - Public routes: 2/2 PASS (GET /health, GET /api/products)
  - Protected routes: 4/4 PASS (401 without token, registration, login JWT, 200 with token)
  - Rate limiting: 1/1 PASS (HTTP 429 burst enforcement)
  - CORS preflight: 1/1 PASS (OPTIONS Access-Control-Allow-Origin: http://localhost:3000)
  - Perimeter isolation: 3/3 PASS (Internal ports 8002 & 8003 blocked from host; unmapped route 404)
  - Kong Admin API: 1/1 PASS (Reachable on 127.0.0.1:8001 loopback)
  - Mock payments: 4/4 PASS (KHQR generation, settlement to PAID, EXPIRED, FAILED)
  - **Overall**: 16/16 tests PASSED (100% success rate, 0 failures).
- **Backend Unit Tests**: 23/23 unit tests pass across `user_service`, `operation_service`, `report_service`.
- **Frontend Code Quality**:
  - `npm run lint`: 0 errors.
  - `npm run type-check`: 0 errors.
  - `npm run build`: Production Next.js build succeeds with static pages generated.

---

## Next Tasks
All prompt phases (Step 0 through Step 5) and deliverables are completed. Ready for user code review.

## Dependencies Added / Removed
- Removed rogue virtual environment package: `MyApplication 0.1.0` (uninstalled via pip).
- Cleaned duplicate dependency in `requirements-dev.txt`.
- No extraneous global dependencies added.

## Blocked Items
- Resolved: Host port 5432 conflict was resolved cleanly by exposing `127.0.0.1:${POSTGRES_HOST_PORT:-5432}:5432`, allowing developers to set `POSTGRES_HOST_PORT=5433` without killing local host processes.

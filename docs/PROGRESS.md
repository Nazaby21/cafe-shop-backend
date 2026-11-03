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
- **Current Step**: STEP 2 COMPLETED -> STARTING STEP 3 (BUG HUNT)
- **Step 0 Completed**: `2026-11-03T19:33:00+07:00`
- **Step 1 Completed**: `2026-11-04T01:41:00+07:00`
- **Step 2 Completed**: `2026-11-04T01:50:00+07:00`
- **Output Artifacts**: `docs/09_DOCKER_BUILD_REPORT.md`, `docs/10_BUG_REPORT.md` (Starting), `docs/build-logs/*.log`

### Step 2 Docker Build Fix Summary
- **Context Bloat & Secret Leak Fixed**: Added `.dockerignore` to `coffee_shop/` and `coffee_shop_frontend/`. Blocked `.env*`, `.venv`, `node_modules`, `__pycache__`, `.git`. Reduced context transfer from 12-58 MB down to 2-45 kB.
- **Production Build Failure Resolved**: Fixed `coffee_shop_frontend/Dockerfile` by creating `public/.gitkeep` and adding defensive `mkdir -p /app/public`.
- **Python Image Footprint Slashed**: Removed unneeded `gcc` and `libpq-dev` (since `psycopg2-binary` precompiled wheels are used). Slashed image sizes from 576-642 MB down to 293 MB each (-50%).
- **Security Hardening**: Configured non-root user `nextjs:1001` in production frontend runner stage.
- **Full Stack Validation**: Both `docker-compose.local.yml` and `docker-compose.yml` build with 0 errors.

---

## Next 3 Tasks
1. **STEP 3 Batch 1 - Backend Bug Audit**: Run `ruff check` and `pytest` across `user_service`, `operation_service`, `report_service`, `libs`. Audit for blocking calls, unhandled exceptions, timezone-naive datetimes, and DB session leaks.
2. **STEP 3 Batch 2 - Frontend Bug Audit**: Run `npm run lint` and `npx tsc --noEmit` in `coffee_shop_frontend`. Audit for hydration mismatches, unhandled promise rejections, and stale polling intervals.
3. **STEP 3 Batch 3 - Gateway & Config Audit**: Validate `kong.yml` route `strip_path` settings against backend router prefixes, CORS configurations, and environment variable bindings.

## Dependencies Added / Removed
- None (zero global packages installed).

## Blocked Items
- Host port 5432 conflict: PID 8544 (`postgres.exe`) is running locally on Windows. Per safety rules ("Do not kill any process"), this process will not be terminated. Compose PostgreSQL port binding may need loopback alternate (e.g. `127.0.0.1:5433:5432`) or documentation in `OPEN_QUESTIONS.md`.

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
- **Current Step**: STEP 1 COMPLETED -> STARTING STEP 2 (FIX DOCKER BUILDS)
- **Step 0 Completed**: `2026-11-03T19:33:00+07:00`
- **Step 1 Completed**: `2026-11-04T01:41:00+07:00`
- **Output Artifacts**: `docs/09_DOCKER_BUILD_REPORT.md` (Table of reproductions & clean worktree analysis), `docs/build-logs/*.log`

### Step 0 Verification Summary
- **Docker Engine**: Docker Desktop 4.98.0 (Engine 29.9.2), Linux container mode, WSL2 kernel (`6.6.87.1-microsoft-standard-WSL2`).
- **Compose**: Docker Compose v5.6.1.
- **BuildKit**: Active via `desktop-linux*` (BuildKit v0.34.0).
- **Resources**: 15.44 GiB RAM, 16 CPUs, 4.01 GB build cache.
- **Port Conflict**: Port 5432 is occupied on the Windows host by PID 8544 (`postgres`). Ports 3000, 8000, 8001, 8002, 8003 are free.
- **Compose Files**: `docker-compose.local.yml` and `docker-compose.yml` validated cleanly from `coffee_shop/`.

### Step 1 Reproduction Summary
- Saved logs in `docs/build-logs/`: `user-service.log`, `operation-service.log`, `report-service.log`, `frontend.log`, `frontend-prod.log`, `full-stack-local.log`.
- **Reproduced Build Failure**: Production `frontend` (`Dockerfile`) fails at step 13 with `"/app/public": not found` because `coffee_shop_frontend` lacks a `public` directory.
- **Defect Identified (Context & Image Bloat)**: Neither `coffee_shop` nor `coffee_shop_frontend` had a `.dockerignore`. This caused host `.venv`, `.env` credentials, `__pycache__`, and host Windows `node_modules` (400MB+) to be copied into images, blowing `frontend` up to 2.63 GB.
- **Defect Identified (Python Slim Images)**: `gcc` and `libpq-dev` installed 225MB of build tooling not needed at runtime since `psycopg2-binary` precompiled wheels are used.

---

## Next 3 Tasks
1. **STEP 2 Fix 1**: Add comprehensive `.dockerignore` files to both `coffee_shop/` and `coffee_shop_frontend/` to block `.env`, `.venv`, `node_modules`, `__pycache__`, and `.git`.
2. **STEP 2 Fix 2**: Fix `coffee_shop_frontend/Dockerfile` by creating `public/` directory with `.gitkeep` and supporting standalone Next.js build.
3. **STEP 2 Fix 3**: Optimize Dockerfile layer caching and image footprint across backend services and frontend.

## Dependencies Added / Removed
- None (zero global packages installed).

## Blocked Items
- Host port 5432 conflict: PID 8544 (`postgres.exe`) is running locally on Windows. Per safety rules ("Do not kill any process"), this process will not be terminated. Compose PostgreSQL port binding may need loopback alternate (e.g. `127.0.0.1:5433:5432`) or documentation in `OPEN_QUESTIONS.md`.

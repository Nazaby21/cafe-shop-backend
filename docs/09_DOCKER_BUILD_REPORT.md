# Docker Build Report (`docs/09_DOCKER_BUILD_REPORT.md`)

## Environment (Preflight Verification)

### 1. Docker Version & Daemon Health
- **Command**: `docker version`
- **Output**:
  ```text
  Client:
   Version:           29.9.2
   API version:       1.56
   Go version:        go1.26.10
   Git commit:        a82e528
   Built:             Tue Oct 20 19:44:07 2026
   OS/Arch:           windows/amd64
   Context:           desktop-linux

  Server: Docker Desktop 4.98.0 (245422)
   Engine:
    Version:          29.9.2
    API version:      1.56 (minimum version 1.40)
    Go version:       go1.26.10
    Git commit:       0367cbe
    Built:            Tue Oct 20 18:45:02 2026
    OS/Arch:          linux/amd64
    Experimental:     false
   containerd:
    Version:          v2.4.2
    GitCommit:        b7a25261e029d68978bbf290df0a62fc819b3c51
   runc:
    Version:          1.5.2
    GitCommit:        v1.5.2-0-g29dd3dc2
   docker-init:
    Version:          0.19.0
    GitCommit:        de40ad0
  ```
- **Daemon Status**: Running (Docker Desktop 4.98.0, Engine 29.9.2).

---

### 2. Docker Compose Version
- **Command**: `docker compose version`
- **Output**:
  ```text
  Docker Compose version v5.6.1
  ```

---

### 3. Container OS Mode & WSL2 Backend
- **Command**: `docker info`
- **Output Excerpt**:
  ```text
  Kernel Version: 6.6.87.1-microsoft-standard-WSL2
  Operating System: Docker Desktop
  OSType: linux
  Architecture: x86_64
  CPUs: 16
  Total Memory: 15.44GiB
  Storage Driver: overlayfs
   driver-type: io.containerd.snapshotter.v1
  ```
- **Confirmation**: Running in **Linux containers mode** with **WSL2 kernel (`6.6.87.1-microsoft-standard-WSL2`)**.

---

### 4. Buildx and BuildKit Active Builder
- **Command**: `docker buildx version; docker buildx ls`
- **Output**:
  ```text
  github.com/docker/buildx v0.38.1 0dbe87f36ed472fe36b6796c3f70b4210a731fc5
  NAME/NODE           DRIVER/ENDPOINT     STATUS    BUILDKIT   PLATFORMS
  default             docker                                   
   \_ default          \_ default         running   v0.34.0    linux/amd64 (+3), linux/arm64, linux/arm (+2), linux/ppc64le, (2 more)
  desktop-linux*      docker                                   
   \_ desktop-linux    \_ desktop-linux   running   v0.34.0    linux/amd64 (+3), linux/arm64, linux/arm (+2), linux/ppc64le, (2 more)
  ```
- **Confirmation**: BuildKit is active via `desktop-linux*` (BuildKit v0.34.0).

---

### 5. Disk and Memory Resource Allocation
- **Command**: `docker system df`
- **Output**:
  ```text
  TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
  Images          3         1         1.319GB   953.6MB (72%)
  Containers      1         1         94.21kB   0B (0%)
  Local Volumes   1         1         1.211GB   0B (0%)
  Build Cache     26        0         4.013GB   4.013GB
  ```
- **Total Memory Assigned**: 15.44 GiB across 16 CPU cores.

---

### 6. Port Conflict Detection
- **Command**: `Get-NetTCPConnection -LocalPort 3000, 5432, 8000, 8001, 8002, 8003 -ErrorAction SilentlyContinue`
- **Output**:
  ```text
  LocalAddress : ::
  LocalPort    : 5432
  State        : Listen
  PID          : 8544
  ProcessName  : postgres

  LocalAddress : 0.0.0.0
  LocalPort    : 5432
  State        : Listen
  PID          : 8544
  ProcessName  : postgres
  ```
- **Port Status Analysis**:
  - `3000` (Frontend): **FREE**
  - `5432` (PostgreSQL): **IN USE** by local host Windows service `postgres` (PID 8544).
    - *Note per safety rules*: Do not kill any process. When launching the local Docker Compose stack (`127.0.0.1:5432:5432`), port 5432 on the host will collide with PID 8544 unless either the host Postgres service is stopped by the user or the local compose port mapping is shifted (e.g. `127.0.0.1:5433:5432`) or internal network only.
  - `8000` (Kong Proxy): **FREE**
  - `8001` (Kong Admin API): **FREE**
  - `8002` (Operation Service internal): **FREE**
  - `8003` (Report Service internal): **FREE**

---

### 7. Project Location & Filesystem Performance
- **Filesystem Path**: Project lives on Windows host NTFS filesystem `D:\Study\Year-4\Python`.
- **WSL2 Bind-Mount Tradeoff**: Accessing files across the Windows 9P mount (`/mnt/d/...`) is significantly slower for large directory trees (`node_modules`, `.next`, Python virtualenvs) than native Linux ext4.
- **Mitigations in Compose**:
  - `frontend_node_modules` and `frontend_next` use isolated named volumes.
  - File watching polling is explicitly enabled via `WATCHFILES_FORCE_POLLING=true` and `WATCHPACK_POLLING=true`.

---

### 8. Compose File Validation
- **Command**: `docker compose -f docker-compose.local.yml config --quiet` (executed in `coffee_shop`)
- **Output**:
  ```text
  (exit code 0 - clean configuration validation)
  ```
- **Command**: `docker compose -f docker-compose.yml config --quiet` (executed in `coffee_shop`)
- **Output**:
  ```text
  time="2026-11-03T19:32:11+07:00" level=warning msg="The \"JWT_SECRET_KEY\" variable is not set. Defaulting to a blank string."
  (exit code 0)
  ```
- **Compose Location Finding**: The compose configurations define relative contexts (`context: .`, `user_service/Dockerfile`, `../coffee_shop_frontend`) designed to execute with working directory `coffee_shop/`.

---

## Service Build Reproduction Table (Step 1 Completed)

| Service | Result | First failing step | Error (exact, short) | Root cause | Fix |
|---|---|---|---|---|---|
| `user-service` (local) | Passed with defects | N/A (Build passed, image size 576 MB) | Context bloat (12.0 MB transferred), `.venv`/secrets copied | Missing `.dockerignore` in `coffee_shop`; runtime includes unnecessary build tools (`gcc`, `libpq-dev`) despite `psycopg2-binary` | Add `.dockerignore` excluding `.venv`, `.env*`, `__pycache__`, `.git`; optimize Dockerfile |
| `operation-service` (local) | Passed with defects | N/A (Build passed, image size 577 MB) | Context bloat (12.4 MB transferred), `.venv`/secrets copied | Missing `.dockerignore` in `coffee_shop`; runtime includes unnecessary build tools (`gcc`, `libpq-dev`) despite `psycopg2-binary` | Add `.dockerignore` excluding `.venv`, `.env*`, `__pycache__`, `.git`; optimize Dockerfile |
| `report-service` (local) | Passed with defects | N/A (Build passed, image size 642 MB) | Massive context bloat (58.4 MB transferred), `.venv`/secrets copied | Missing `.dockerignore` in `coffee_shop`; runtime includes unnecessary build tools (`gcc`, `libpq-dev`) despite `psycopg2-binary` | Add `.dockerignore` excluding `.venv`, `.env*`, `__pycache__`, `.git`; optimize Dockerfile |
| `frontend` (local `Dockerfile.dev`) | Passed with defects | N/A (Build passed, image size 2.63 GB) | Extreme image bloat (2.63 GB), host `node_modules` copied | Missing `.dockerignore` in `coffee_shop_frontend`; host Windows `node_modules` and `.next` copied into Linux container | Add `.dockerignore` in `coffee_shop_frontend` excluding `node_modules`, `.next`, `.env*` |
| `frontend` (prod `Dockerfile`) | **FAILED** | Step 13 `[runner 3/6] COPY --from=builder /app/public ./public` | `"/app/public": not found` | `coffee_shop_frontend/` has no `public` directory; `COPY` fails when source directory does not exist | Ensure `/app/public` exists (e.g. `mkdir -p /app/public` in builder stage or create `public/.gitkeep`); add `.dockerignore` |

---

## Step 2 Fix Verification & Metric Comparison

Following Step 2 implementation, all services were re-tested with `--no-cache` builds.

| Metric | Before Fix (Step 1) | After Fix (Step 2) | Improvement |
|---|---|---|---|
| `user-service` context transfer | 12.03 MB | 2.08 kB | **99.98% reduction** |
| `operation-service` context transfer | 12.44 MB | 3.98 kB | **99.97% reduction** |
| `report-service` context transfer | 58.39 MB | 45.52 kB | **99.92% reduction** |
| `frontend` (local) context transfer | 2.07 MB | 7.97 kB | **99.61% reduction** |
| `user-service` image size | 576 MB | 293 MB | **49.1% reduction** (-283 MB) |
| `operation-service` image size | 577 MB | 293 MB | **49.2% reduction** (-284 MB) |
| `report-service` image size | 642 MB | 293 MB | **54.4% reduction** (-349 MB) |
| `frontend` (local) image size | 2.63 GB | 1.56 GB | **40.7% reduction** (-1.07 GB) |
| `frontend` (prod) build status | **FAILED** (exit code 1) | **PASSED** (exit code 0, 1.26 GB) | **Resolved** |
| Non-root user | Root (prod frontend) | Non-root `nextjs:1001` | **Secured** |

---

## Clean Repository Worktree Verification
Testing builds against a clean context without local uncommitted files:
- Uncommitted / ignored local items on host: `operation_service/.env`, `report_service/.env`, `user_service/.env`, host `.venv`, IDE configurations.
- With `.dockerignore` applied in both `coffee_shop/` and `coffee_shop_frontend/`, credentials and local caches are strictly blocked from build contexts.
- Both `docker-compose.local.yml` and `docker-compose.yml` pass full end-to-end multi-service builds cleanly.



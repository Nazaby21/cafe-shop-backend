# Step 1: Kong Gateway & SQLite Discovery Report (`docs/05_KONG_DISCOVERY.md`)

> **Executive Summary**: This discovery audits the current microservice architecture, port topology, frontend client routing, and all traces of SQLite across the codebase to prepare for complete SQLite eradication (PostgreSQL only) and Kong Gateway (OSS) DB-less reverse proxy integration.

---

## 1. Services Inventory, Ports, and Database Usage

The backend platform consists of three core FastAPI microservices and one Next.js App Router frontend:

| Service | Target Port | Current Database Config | DB Engine & Driver | Direct Frontend Client (`axios.ts`) |
| :--- | :--- | :--- | :--- | :--- |
| **`user_service`** | `8001` | `user_service_db` on PostgreSQL (`port 5432`) | SQLAlchemy 2.0 + `psycopg2-binary` | `authClient` (`NEXT_PUBLIC_AUTH_API_URL`) |
| **`operation_service`** | `8002` | `operation_service_db` on PostgreSQL (`port 5432`) | SQLAlchemy 2.0 + `psycopg2-binary` | `operationClient` (`NEXT_PUBLIC_OPERATION_API_URL`) |
| **`report_service`** | `8003` | `report_service_db` on PostgreSQL (`port 5432`) | SQLAlchemy 2.0 + `psycopg2-binary` | `reportClient` (`NEXT_PUBLIC_REPORT_API_URL`) |
| **`coffee_shop_frontend`** | `3000` | Browser `localStorage` + session cookie | Client React 19 / Zustand 5 / Next.js 15 | Origin (`http://localhost:3000`) |

### How the Frontend Reaches Services Today
1. **No Single Gateway**: The frontend directly connects to three distinct backend origins defined in `coffee_shop_frontend/src/config/env.ts`:
   - `NEXT_PUBLIC_AUTH_API_URL` (e.g. `http://localhost:8001`)
   - `NEXT_PUBLIC_OPERATION_API_URL` (e.g. `http://localhost:8002`)
   - `NEXT_PUBLIC_REPORT_API_URL` (e.g. `http://localhost:8003`)
2. **CORS Exposure**: Because each service is queried directly by browser clients, all three services must enable `CORSMiddleware` with broad allowances, exposing internal ports and complicating cookie/session handling.
3. **Port Sprawl**: Deploying to AWS EC2 currently requires opening ports 8001, 8002, 8003, and 3000 or juggling reverse proxies. Kong Gateway will replace this with a single public entry point (`NEXT_PUBLIC_API_BASE_URL` on port `8000` or `80`).

---

## 2. Complete SQLite Usage Audit

An exhaustive scan across all files, code, tests, and configuration identified the following SQLite references:

### 2.1 Application Core Code (`app/core/database.py`)
All three backend services contain boilerplate in their `app/core/database.py` that checks for SQLite and sets `connect_args["check_same_thread"] = False`:
- `coffee_shop/user_service/app/core/database.py`: Lines 8–9
- `coffee_shop/operation_service/app/core/database.py`: Lines 8–9
- `coffee_shop/report_service/app/core/database.py`: Lines 8–9

```python
# Legacy SQLite compatibility hook to be removed:
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
```

### 2.2 Test Suites & Pytest Configuration (`tests/conftest.py`)
The unit and integration test fixtures currently default to in-memory SQLite (`sqlite:///:memory:`) using `StaticPool`:
- `coffee_shop/user_service/tests/conftest.py`: Lines 6, 21, 25
- `coffee_shop/operation_service/tests/conftest.py`: Lines 6, 17, 21
- `coffee_shop/report_service/tests/conftest.py`: Lines 6, 17, 21

```python
# Legacy in-memory SQLite test configuration to be replaced with PostgreSQL:
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
```

### 2.3 Cross-Service Integration Runner (`scripts/run_integration_check.py`)
The end-to-end integration test runner creates temporary disk-based SQLite databases in a `tempfile.TemporaryDirectory`:
- `coffee_shop/scripts/run_integration_check.py`: Lines 29–31, 53, 76, 117, 155, 169, 182
  - `u_db = tmp_path / "user_itest.db"` (`sqlite:///{u_db}`)
  - `o_db = tmp_path / "operation_itest.db"` (`sqlite:///{o_db}`)
  - `r_db = tmp_path / "report_itest.db"` (`sqlite:///{r_db}`)

### 2.4 Physical Database Files in Workspace Root
Three SQLite binary database files exist in the repository root `coffee_shop/`:
- `coffee_shop/user_service.db` (40 KB)
- `coffee_shop/operation_service.db` (48 KB)
- `coffee_shop/report_service.db` (40 KB)

**Row Count Inspection**:
- `user_service.db`: `users` = **0 rows**.
- `operation_service.db`: `categories` = 0, `products` = 0, `orders` = 0, `payments` = 0, `stock_movements` = 0, customizations = 0 (**0 rows**).
- `report_service.db`: `users_snapshot` = 0, `products_snapshot` = 0, `orders_snapshot` = 0, `order_items_snapshot` = 0 (**0 rows**).

*Conclusion*: No operational data exists in these files. Data migration is skipped, and these files will be archived and safely unlinked.

### 2.5 Documentation & Ignore Files
- `coffee_shop/.gitignore`: Lists `*.db`, `*.sqlite*`, `*.sqlite3`.
- `coffee_shop/docs/01_ARCHITECTURE.md` & `04_CLEANUP_REPORT.md`: Highlighted stale SQLite files for removal.

---

## 3. Plan for Transition

1. **Step 2 (SQLite Removal)**:
   - Remove `check_same_thread` and `sqlite` condition branches from all `app/core/database.py`.
   - Require PostgreSQL in `app/core/config.py` (reject `sqlite://`).
   - Configure pytest and integration runners to run against dedicated PostgreSQL test databases or schemas.
   - Author single Docker Compose service for PostgreSQL with healthchecks and auto-initialization of `user_service_db`, `operation_service_db`, and `report_service_db`.
2. **Step 3 (Kong Gateway OSS Implementation)**:
   - Introduce DB-less Kong 3.9 OSS with `kong.yml` declarative configuration.
   - Configure routes:
     - `/api/auth` -> `user_service:8001` (`/user`)
     - `/api/orders` & `/api/products` & `/api/categories` & `/api/payments` -> `operation_service:8002`
     - `/api/reports` -> `report_service:8003` (`/report`)
   - Implement plugins: CORS, Request Size Limiting, Correlation ID (`X-Request-ID`), Local Rate-Limiting (`policy: local`), and JWT / Key authentication.
   - Update Next.js frontend to use unified `NEXT_PUBLIC_API_BASE_URL`.
   - Ensure Mock Bakong payment switch (`BAKONG_MODE=mock`) remains deterministic and offline.

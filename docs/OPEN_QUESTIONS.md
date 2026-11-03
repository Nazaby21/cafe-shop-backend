# Open Questions, Official Spec Discrepancies & Architectural Assumptions (`docs/OPEN_QUESTIONS.md`)

> Per unattended execution rules, every question or discrepancy between common payment gateway assumptions and the **official NBC Bakong Open API & KHQR specification**, as well as Kong APIM and PostgreSQL architectural decisions, is documented here along with the engineering assumption applied.

---

## 1. Official Bakong Open API Spec Findings vs Common Assumptions

### Q1: Does Bakong Open API provide a Push Webhook / Callback when a KHQR is paid?
- **Official NBC Documentation Reality**: **No.** The official NBC Bakong Open API (`https://api-bakong.nbc.gov.kh/v1/*`) does **not** push server-to-server webhooks upon KHQR payment completion. Instead, integrators must poll `POST /v1/check_transaction_by_md5` (single) or `POST /v1/check_transaction_by_md5_list` (batch up to 50 MD5 hashes).
- **Assumption & Design Decision**: We designed and implemented a **PostgreSQL `FOR UPDATE SKIP LOCKED` background verification worker** (`verification_jobs` table) with adaptive backoff (3s -> 5s -> 10s), batch MD5 verification (`check_transaction_by_md5_list`), a 60-second late-payment reconciliation job, and an on-demand rate-limited `POST /order/{order_id}/payment/verify` endpoint for immediate client checks.

### Q2: Does Bakong Open API provide a Programmatic Refund Endpoint?
- **Official NBC Documentation Reality**: **No.** Bakong Open API v1 is a QR generation + transaction verification API (`renew_token`, `generate_deeplink_by_qr`, `check_transaction_by_md5`, `check_transaction_by_account_id`, `check_bakong_account`). It does not expose a programmatic reversal/refund transfer endpoint.
- **Assumption & Design Decision**: Refunds are processed **manual/off-gateway** by store staff/admin via their Bakong Merchant App or acquiring bank portal, and then recorded in our system via `POST /order/{order_id}/payment/refund` with the Bakong transfer reference (`external_refund_ref`), transitioning the payment to `refunded` and logging an immutable `payment.refunded` audit event in `payment_events`.

### Q3: Cambodia Geo-IP Filtering on `https://api-bakong.nbc.gov.kh`
- **Official NBC Network Behavior**: NBC's production gateway (`api-bakong.nbc.gov.kh`) enforces strict perimeter filtering and typically drops or blocks requests originating from non-Cambodian cloud data centers (e.g., AWS Singapore, US/EU regions) unless the egress static IP is whitelisted with NBC or routed through a Cambodian ISP/VPS.
- **Assumption & Design Decision**: We implemented `BakongClientInterface` with `MockBakongClient` and `RealBakongClient` switchable via `BAKONG_MODE=mock|sandbox` (default `mock`). In mock mode, 100% of payment generation, MD5 calculations, and simulation endpoints run offline with zero outbound HTTP requests.

---

## 2. Project-Specific Architectural Questions & Assumptions

### Q4: Dedicated `payment-service` vs Existing `operation_service` Payment Routes
- **Assumption & Design Decision**: Full Bakong KHQR generation, CRC16/MD5, verification worker (`SKIP LOCKED`), Alembic migrations, and payment routes are modularized in `operation_service`, with routes exposed through Kong Gateway at both `/api/orders/{id}/payment` and `/api/payments`.

### Q5: Settlement Currency (USD vs KHR) and Exchange Rate
- **Assumption & Design Decision**: Default KHQR currency is `USD` (matching `orders.total_amount`). When `currency="KHR"` is requested, we convert using configurable `BAKONG_USD_TO_KHR_RATE` (default `4100` KHR per `1.00 USD`, rounded to integer KHR with 0 decimal places as required by EMVCo Tag `54` for ISO `116`).

### Q6: Staff Offline Cash Payments vs "ONLY Bakong KHQR"
- **Assumption & Design Decision**: All third-party online card/wallet gateways (`card`, `e_wallet`, ABA PayWay, Stripe, etc.) are removed/excluded. Online checkout uses **exclusively Bakong KHQR** (`method="khqr"`). Staff/admin can still advance orders via `PATCH /order/{id}/status` as required by existing integration tests.

---

## 3. Kong Gateway & Database Transition Decisions

### Q7: Kong DB-less Mode vs PostgreSQL Mode
- **Decision**: Pinned Kong Gateway OSS 3.9 in **DB-less mode** (`KONG_DATABASE=off`) with declarative configuration in `kong/kong.yml`.
- **Rationale**: Eliminates the operational overhead of a 4th database schema, avoids migration race conditions during container boot, and keeps the gateway entirely stateless and version-controlled in git.

### Q8: Rate Limiting Policy Without Redis
- **Decision**: Configured Kong Rate Limiting with `policy: local`.
- **Rationale**: Redis is strictly prohibited by architectural constraints. Local in-memory rate limiting operates within Kong's shared memory dictionary (`lua_shared_dict`), enforcing client limits per container with zero external cache dependency.

### Q9: Gateway vs Service-Level JWT Authentication
- **Decision**: Perimeter routing, rate-limiting, and CORS at Kong Gateway; cryptographic JWT verification and fine-grained RBAC in FastAPI microservice dependencies (`get_current_user`, `require_roles`).
- **Rationale**: Keeps Kong DB-less and lightweight without static consumer keys; preserves fine-grained domain authorization (such as checking if an order belongs to the requesting customer); ensures consistent `ApiResponse` error structures.

### Q10: Legacy SQLite Binary Files Row Count
- **Verification**: `user_service.db`, `operation_service.db`, and `report_service.db` were inspected via python `sqlite3`. All tables had **0 rows**.
- **Action**: No data extraction or schema migration script needed; all models and migrations are defined in SQLAlchemy and Alembic. Database files are listed in `CLEANUP_REPORT_SQLITE.md` and safely marked for deletion.

---

## 4. Local Docker Desktop & Windows Development Stack Decisions

### Q11: Windows Drive Bind Mounts & Inotify Event Propagation
- **Problem**: Mounting directories from Windows NTFS (`D:\...`) into Linux containers via Docker Desktop / WSL2 uses 9P filesystem translation, which frequently fails to deliver Linux kernel `inotify` change events to processes inside containers.
- **Decision**: Explicitly configured `WATCHFILES_FORCE_POLLING=true` in FastAPI services and `WATCHPACK_POLLING=true` in Next.js.
- **Tradeoff**: Increases CPU usage slightly (typically ~1-2%), but guarantees reliable hot-reloading across Windows file edits without restarting containers.

### Q12: Anonymous Container Volumes for `node_modules` and `.venv`
- **Problem**: If the root workspace is mounted into a Linux container (`- .:/app`), the host Windows directory will overwrite the container's Linux-compiled `node_modules` and Python `.venv` binaries, causing ELF/PE binary mismatch errors.
- **Decision**: Configured anonymous / named volumes over `/app/node_modules`, `/app/.next`, and `/app/.venv`.
- **Outcome**: The container retains Linux-native binaries and dependencies, while all TypeScript/Python source files remain live-synced from the Windows host.

### Q13: Next.js SSR Dual Endpoint Resolution
- **Problem**: Next.js code executing on the browser must call `http://localhost:8000` (which resolves on the user's host machine to Kong). If that same code executes on the server side (SSR, Server Components) inside the container, `http://localhost:8000` attempts to connect to the frontend container itself and fails with `ECONNREFUSED`.
- **Decision**: Updated `coffee_shop_frontend/src/config/env.ts` and `src/services/axios.ts` to inspect `typeof window === 'undefined'`. Client-side requests route to `NEXT_PUBLIC_API_BASE_URL` (`http://localhost:8000`); server-side container requests route to `INTERNAL_API_BASE_URL` (`http://kong:8000`).

### Q14: Strict 127.0.0.1 Loopback Host Binding
- **Problem**: Default compose port bindings like `8000:8000` bind to `0.0.0.0:8000`, exposing the local gateway and dev database to the local LAN or Wi-Fi network.
- **Decision**: All published ports in `docker-compose.local.yml` explicitly bind to `127.0.0.1` (`127.0.0.1:8000:8000`, `127.0.0.1:8001:8001`, `127.0.0.1:5432:5432`, `127.0.0.1:3000:3000`). Internal microservices publish NO host ports.
- **Outcome**: Strict local developer security perimeter with zero external LAN attack surface.


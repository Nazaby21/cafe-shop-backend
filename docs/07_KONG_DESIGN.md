# Step 3: Kong Gateway APIM Design & Architecture Report (`docs/07_KONG_DESIGN.md`)

> **Executive Summary**: This document specifies the single API Gateway entry point (APIM) implemented with Kong Gateway OSS 3.9 in DB-less declarative mode. All client requests from the Next.js frontend route through a single public port (`8000`), terminating CORS, enforcing rate limits without Redis, injecting distributed tracing headers (`X-Request-ID`), and routing traffic to internal FastAPI microservices isolated within a private Docker bridge network.

---

## 1. APIM Architecture & Topology

```
+--------------------------------------------------------------------------+
|                        PUBLIC INTERNET / HOST                            |
|                                                                          |
|     +-------------------------+             +----------------------+     |
|     |   Next.js 15 Frontend   |             |   External Clients   |     |
|     |  (http://localhost:3000)|             |  (curl, postman, POS)|     |
|     +------------+------------+             +----------+-----------+     |
+------------------|-------------------------------------|-----------------+
                   |                                     |
                   +------------------+------------------+
                                      |
                           HTTP (Port 8000)
                                      v
+--------------------------------------------------------------------------+
|                   KONG GATEWAY OSS 3.9 (DB-Less Mode)                    |
|                                                                          |
|   Global Ingress Plugins:                                                |
|     1. CORS (origins: *, credentials: true)                              |
|     2. Correlation ID (X-Request-ID: uuid#counter)                       |
|     3. Request Size Limiting (max 10MB payload)                          |
|     4. Rate Limiting (policy: local in-memory, 100 req/min global)       |
|     5. Route Rate Limiting (10 req/min on login, 20 req/min on payments) |
+----+-------------------+-----------------------+--------------------+----+
     |                   |                       |                    |
     | /api/auth/*       | /api/orders/*         | /api/reports/*     | /health
     |                   | /api/products/*       |                    |
     |                   | /api/categories/*     |                    |
     |                   | /api/payments/*       |                    |
     v                   v                       v                    v
+----------------+ +--------------------+ +-----------------+  (Gateway
|  user-service  | | operation-service  | | report-service  |   Health)
|  (Port 8001)   | | (Port 8002)        | | (Port 8003)     |
|                | | + MockBakongClient | |                 |
+--------+-------+ +---------+----------+ +--------+--------+
         |                   |                     |
         +-------------------+---------------------+
                             |
                   PostgreSQL Connection Pool
                             v
+--------------------------------------------------------------------------+
|                     POSTGRESQL 16 (Port 5432 Internal)                   |
|                                                                          |
|   +---------------------+ +----------------------+ +-----------------+   |
|   |   user_service_db   | | operation_service_db | |report_service_db|   |
|   +---------------------+ +----------------------+ +-----------------+   |
+--------------------------------------------------------------------------+
```

---

## 2. Kong Routing & Upstream Services Mapping Table

All microservices are internal to Docker (`coffee_network`). Host ports 8001, 8002, 8003, and 5432 are **not bound to host interfaces**, ensuring zero perimeter bypass.

| Ingress Route Path | Upstream Service Target | `strip_path` | HTTP Methods Allowed | Plugins Applied | Upstream Service Endpoint |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`/api/auth/login`** | `http://user-service:8001/user/login` | `true` | `POST` | Rate Limiting (10/min, `policy: local`) | Authenticate user & issue JWT |
| **`/api/auth`** | `http://user-service:8001/user` | `true` | `GET`, `POST`, `OPTIONS` | Global (100/min), CORS, Tracing | User registration (`POST`) & listing (`GET`) |
| **`/api/auth/{id}`** | `http://user-service:8001/user/{id}` | `true` | `GET`, `PUT`, `PATCH`, `DELETE` | Global (100/min), CORS, Tracing | User profile, update, role, password |
| **`/api/orders`** | `http://operation-service:8002/order` | `true` | `GET`, `POST`, `PATCH`, `OPTIONS` | Global (100/min), CORS, Tracing | Create/list/update customer orders |
| **`/api/orders/{id}/payment`** | `http://operation-service:8002/order/{id}/payment` | `true` | `GET`, `POST`, `OPTIONS` | Global (100/min), CORS, Tracing | Generate dynamic KHQR & query payment |
| **`/api/products`** | `http://operation-service:8002/product` | `true` | `GET`, `POST`, `PUT`, `DELETE` | Global (100/min), CORS, Tracing | Browse catalog (public) & manage products |
| **`/api/categories`** | `http://operation-service:8002/category` | `true` | `GET`, `POST`, `PUT`, `DELETE` | Global (100/min), CORS, Tracing | List/create categories |
| **`/api/payments`** | `http://operation-service:8002/payment` | `true` | `GET`, `POST`, `OPTIONS` | Rate Limiting (20/min, `policy: local`) | Payment queries & mock payment triggers |
| **`/api/payments/mock-pay/{md5}`**| `http://operation-service:8002/payment/mock-pay/{md5}` | `true` | `POST` | Rate Limiting (20/min), CORS | Immediate test settlement (mock mode) |
| **`/api/reports`** | `http://report-service:8003/report` | `true` | `GET`, `POST`, `OPTIONS` | Global (100/min), CORS, Tracing | Sales/user analytics & sync trigger |
| **`/health`** | `http://operation-service:8002/health` | `true` | `GET` | CORS | Gateway & Postgres connectivity check |
| **`/health/user`** | `http://user-service:8001/health` | `true` | `GET` | CORS | User service DB health |
| **`/health/operation`** | `http://operation-service:8002/health` | `true` | `GET` | CORS | Operation service DB health |
| **`/health/report`** | `http://report-service:8003/report` | `true` | `GET` | CORS | Report service DB health |

---

## 3. Kong Plugins Architecture (OSS)

All configured plugins are native open-source plugins that require no Redis or enterprise license.

### 3.1 Rate Limiting (`policy: local`)
Because Redis is strictly prohibited by architectural constraints, rate limiting is configured with `policy: local`:
- Counters are tracked in Kong’s shared nginx memory zone (`lua_shared_dict`).
- Global default: `100 requests / minute` per client IP.
- Sensitive endpoints:
  - `/api/auth/login`: `10 requests / minute` to defend against credential brute-forcing.
  - `/api/payments`: `20 requests / minute` to protect against denial-of-service on payment generation.
- Headers returned downstream: `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`, `X-RateLimit-Limit-Minute`.

### 3.2 CORS Configuration
The CORS plugin terminates cross-origin negotiations at the gateway:
- `origins`: `*`, `http://localhost:3000`, `http://127.0.0.1:3000`.
- `credentials`: `true` (enables cookies and Authorization headers).
- `methods`: `GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD`.
- `headers`: `Accept, Content-Type, Authorization, X-Request-ID`.
- `max_age`: `3600` seconds (1 hour preflight cache).

### 3.3 Correlation ID (`X-Request-ID`)
Distributed request tracing is guaranteed:
- If client sends `X-Request-ID`, Kong preserves and propagates it.
- If omitted, Kong generates a unique `uuid#counter` string.
- Injected downstream to upstream microservices and returned to client in response headers (`echo_downstream: true`).

### 3.4 Request Size Limiting
- `allowed_payload_size`: `10MB`
- Rejects oversized requests with HTTP 413 before upstream ingestion.

---

## 4. Authentication Architecture: Gateway vs Service-Level Decision

### The Decision: Perimeter Routing + Service-Level Defense-in-Depth

| Architectural Factor | Gateway JWT Termination (Kong Plugin) | Service-Level JWT Verification (Chosen Architecture) |
| :--- | :--- | :--- |
| **Kong DB-Less Compatibility** | Requires static consumer configs with `iss` keys hardcoded in `kong.yml`. Inflexible for dynamically generated user keys. | **Native & frictionless in DB-less mode**; Kong handles routing/limits without state. |
| **Fine-Grained RBAC** | Gateway only checks signature. Cannot check resource ownership (e.g. `order.user_id == current_user.id`). | **Services perform full RBAC & ownership** (`admin`, `staff`, `customer`). |
| **Public vs Protected Route Granularity** | Requires complex route splitting in `kong.yml` for every public vs private subpath (e.g. public `/product` catalog vs admin `/product` creation). | **FastAPI dependencies** (`get_current_user`, `require_roles`) handle mixed routes cleanly. |
| **Error Contract Consistency** | Returns generic Kong JSON error format (`{"message": "Unauthorized"}`). | Returns standardized API response envelope (`ApiResponse[T]` with error code and validation details). |

**Conclusion**: Kong acts as the high-throughput perimeter gateway (CORS, Rate Limiting, Request Size, Tracing, Path Routing), while FastAPI microservices enforce cryptographic JWT verification and domain-level authorization via shared `JWT_SECRET_KEY`.

---

## 5. Mock Bakong Switch & Test Automation

To honor the constraint that the Bakong account has only been requested and no real transactions must be called:
1. **Interface/Adapter Pattern**:
   - `BakongClientInterface` defines the contract (`renew_token`, `check_transaction_by_md5`, `check_transaction_by_md5_list`, `generate_deeplink`, `simulate_payment`).
   - `RealBakongClient` makes HTTP calls to NBC Bakong Open API (`https://sit-api-bakong.nbc.gov.kh`).
   - `MockBakongClient` operates 100% in-memory with zero outbound network calls.
2. **Switch via `BAKONG_MODE`**:
   - `BAKONG_MODE=mock` (default): returns mock KHQR, returns successful MD5 results for simulated payments.
   - `BAKONG_MODE=sandbox`: calls NBC Bakong SIT sandbox API.
3. **Instant Test Settlement Endpoint**:
   - `POST /api/payments/mock-pay/{md5}`
   - Automatically registers the MD5 transaction and triggers `PaymentVerificationWorker.verify_payment_now()` to immediately advance order status to `paid`.
   - Returns HTTP 403 Forbidden if `BAKONG_MODE != 'mock'`.

---

## 6. End-to-End Request Flow Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer (Next.js Frontend)
    participant Kong as Kong Gateway OSS (Port 8000)
    participant UserSvc as user-service (Port 8001)
    participant OpSvc as operation-service (Port 8002)
    participant PG as PostgreSQL (Port 5432)

    Note over Customer,Kong: 1. Authentication
    Customer->>Kong: POST /api/auth/login {email, password}
    Kong->>Kong: Apply Rate Limit (10/min) & Correlation ID
    Kong->>UserSvc: POST /user/login
    UserSvc->>PG: SELECT * FROM users WHERE email=...
    UserSvc-->>Kong: 200 OK {access_token: "JWT..."}
    Kong-->>Customer: 200 OK {access_token, X-Request-ID}

    Note over Customer,Kong: 2. Browse Products & Create Order
    Customer->>Kong: GET /api/products
    Kong->>OpSvc: GET /product
    OpSvc->>PG: SELECT * FROM products WHERE is_active=true
    OpSvc-->>Kong: 200 OK {products: [...]}
    Kong-->>Customer: 200 OK

    Customer->>Kong: POST /api/orders {items: [...]} (Bearer JWT)
    Kong->>OpSvc: POST /order (Bearer JWT)
    OpSvc->>PG: INSERT INTO orders ... (status: pending)
    OpSvc-->>Kong: 200 OK {order_id: 42, total: 9.00}
    Kong-->>Customer: 200 OK

    Note over Customer,Kong: 3. Dynamic KHQR Generation
    Customer->>Kong: POST /api/orders/42/payment {method: "khqr", currency: "USD"}
    Kong->>OpSvc: POST /order/42/payment
    OpSvc->>OpSvc: Generate EMVCo KHQR + CRC16 + MD5
    OpSvc->>PG: INSERT INTO payments & verification_jobs
    OpSvc-->>Kong: 200 OK {qr_string, qr_md5, status: "pending"}
    Kong-->>Customer: 200 OK (Displays KHQR with 3-minute countdown)

    Note over Customer,Kong: 4. Mock Payment Simulation (BAKONG_MODE=mock)
    Customer->>Kong: POST /api/payments/mock-pay/{qr_md5}
    Kong->>OpSvc: POST /payment/mock-pay/{qr_md5}
    OpSvc->>OpSvc: MockBakongClient.simulate_payment(qr_md5)
    OpSvc->>OpSvc: PaymentVerificationWorker.verify_payment_now()
    OpSvc->>PG: UPDATE payments SET status='paid'; UPDATE orders SET status='paid'
    OpSvc-->>Kong: 200 OK {status: "paid", order_id: 42}
    Kong-->>Customer: 200 OK (UI updates order to paid immediately)
```

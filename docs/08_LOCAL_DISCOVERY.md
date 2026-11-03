# Step 1: Local Docker vs EC2 Discovery Report (`docs/08_LOCAL_DISCOVERY.md`)

> **Executive Summary**: This discovery audit inventories all AWS EC2-specific configurations, artifacts, and production assumptions across the repository, contrast them against the local Windows Docker Desktop + WSL2 environment requirements, and catalogs all services, ports, environment variables, and build strategies.

---

## 1. Inventory of AWS EC2-Specific Configurations in Repo

| Category | EC2 / Production Configuration | Repository Location | Local Development Replacement | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **Public Host Ports** | `8000:8000` and `3000:3000` bound to `0.0.0.0` (all interfaces) | `docker-compose.yml:137,161` | Bind strictly to `127.0.0.1:8000:8000` and `127.0.0.1:3000:3000` | **MUST** |
| **PostgreSQL Access** | Internal port `5432` only exposed to Docker network | `docker-compose.yml:27-28` | Expose to host loopback `127.0.0.1:5432:5432` for Windows DBeaver / psql inspection | **MUST** |
| **Kong Admin API** | `127.0.0.1:8001:8001` tunneled via SSH over public IP | `docs/EC2_SETUP_GUIDE.md:98-105` | Directly accessible on host loopback `127.0.0.1:8001` (never `0.0.0.0`) | **MUST** |
| **AWS SSH Key & Permissions** | `python-lap.pem` with Windows `icacls` NTFS permission restrictions | `D:\Study\Year-4\Python\APIM-setup\python-lap.pem` | Not used in local workflow; remains git-ignored | **NICE-TO-HAVE** |
| **AWS Region & Public IP** | `ap-southeast-2` (Sydney), Elastic IP allocation, Security Groups (ports 22, 8000, 3000) | `docs/EC2_SETUP_GUIDE.md:10-64` | Localhost / 127.0.0.1 loopback only | **MUST** |
| **Host Firewall (UFW)** | Ubuntu UFW rules (`ufw allow 22`, `8000`, `3000`) | `docs/EC2_SETUP_GUIDE.md:143-149` | Windows Defender Firewall / Docker Desktop WSL2 loopback | **MUST** |
| **Restart Policies** | `restart: unless-stopped` on all 5 containers | `docker-compose.yml:10,38,63,95,123,157` | `restart: no` or `unless-stopped` (development mode) | **SHOULD** |
| **Code Mounting & Hot Reload** | Source baked into container images; no bind mounts | `Dockerfile` (all services) | Host folder bind-mounts + `uvicorn --reload` + Next.js `npm run dev` | **MUST** |
| **Frontend Runtime** | Multi-stage production build (`npm run build`, `npm start`) | `coffee_shop_frontend/Dockerfile` | Node 20 dev server (`npm run dev`) with isolated `node_modules` volume | **MUST** |
| **Line Endings (CRLF)** | Windows default CRLF line endings break Linux entrypoints (`bad interpreter`) | Windows filesystem | `.gitattributes` enforcing `* text=auto` and `*.sh text eol=lf` | **MUST** |
| **Bakong KHQR Mode** | `BAKONG_MODE=mock` (retained offline) | `.env.example`, `docker-compose.yml` | Retained offline `BAKONG_MODE=mock` | **MUST** |

---

## 2. Microservice Build & Runtime Inventory

### 2.1 Database (`postgres`)
- **Base Image**: `postgres:16-alpine` (pinned version, no latest)
- **Role**: Shared RDBMS hosting isolated microservice databases
- **Host Port**: `127.0.0.1:5432:5432` (loopback only)
- **Internal Port**: `5432`
- **Volume Mounts**:
  - `postgres_data:/var/lib/postgresql/data` (persistent named volume)
  - `./postgres/init-databases.sh:/docker-entrypoint-initdb.d/init-databases.sh:ro`
- **Healthcheck**: `pg_isready -U ${DB_USER:-postgres} -d postgres` (5s interval, 5s timeout, 5 retries)
- **Environment Variables**:
  - `POSTGRES_USER`: Database superuser (default `postgres`)
  - `POSTGRES_PASSWORD`: Database password (default `postgres`)
  - `POSTGRES_DB`: Default database (`postgres`)
- **Databases Initialized**: `user_service_db`, `operation_service_db`, `report_service_db` + test databases (`user_service_test_db`, `operation_service_test_db`, `report_service_test_db`)

### 2.2 User Service (`user-service`)
- **Build Context**: `.` (repo root)
- **Dockerfile**: `user_service/Dockerfile` (local dev uses command override for `uvicorn --reload`)
- **Internal Port**: `8001` (NO host port published)
- **Dependencies**: `postgres` (`condition: service_healthy`)
- **Hot Reload**:
  - Bind mounts: `./user_service:/app/user_service`, `./libs:/app/libs`
  - Container volume: `/app/.venv` (protects Linux virtualenv from host overwrite)
  - Polling flag: `WATCHFILES_FORCE_POLLING=true` (ensures change detection on Windows/WSL2 9P bind mounts)
- **Environment Variables**:
  - `ENVIRONMENT=local`
  - `DB_HOST=postgres`, `DB_PORT=5432`, `DB_NAME=user_service_db`
  - `DB_USER=postgres`, `DB_PASSWORD=postgres`
  - `JWT_SECRET_KEY=<shared-secret>`
  - `JWT_ALGORITHM=HS256`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60`
  - `CORS_ORIGINS=*`
- **Healthcheck**: `curl -f http://localhost:8001/health || exit 1`

### 2.3 Operation Service (`operation-service`)
- **Build Context**: `.` (repo root)
- **Dockerfile**: `operation_service/Dockerfile` (local dev uses command override for `uvicorn --reload`)
- **Internal Port**: `8002` (NO host port published)
- **Dependencies**: `postgres` (`condition: service_healthy`)
- **Hot Reload**:
  - Bind mounts: `./operation_service:/app/operation_service`, `./libs:/app/libs`
  - Container volume: `/app/.venv`
  - Polling flag: `WATCHFILES_FORCE_POLLING=true`
- **Environment Variables**:
  - `ENVIRONMENT=local`
  - `DB_HOST=postgres`, `DB_PORT=5432`, `DB_NAME=operation_service_db`
  - `DB_USER=postgres`, `DB_PASSWORD=postgres`
  - `JWT_SECRET_KEY=<shared-secret>`
  - `JWT_ALGORITHM=HS256`
  - `BAKONG_MODE=mock` (strictly offline simulation)
  - `BAKONG_ACCOUNT_ID`, `BAKONG_MERCHANT_NAME`, `BAKONG_MERCHANT_CITY`, `BAKONG_STORE_LABEL`, `BAKONG_TERMINAL_LABEL`, `BAKONG_TOKEN`, `BAKONG_REGISTERED_EMAIL`
  - `CORS_ORIGINS=*`
- **Healthcheck**: `curl -f http://localhost:8002/health || exit 1`

### 2.4 Report Service (`report-service`)
- **Build Context**: `.` (repo root)
- **Dockerfile**: `report_service/Dockerfile` (local dev uses command override for `uvicorn --reload`)
- **Internal Port**: `8003` (NO host port published)
- **Dependencies**: `postgres` (`condition: service_healthy`)
- **Hot Reload**:
  - Bind mounts: `./report_service:/app/report_service`, `./libs:/app/libs`
  - Container volume: `/app/.venv`
  - Polling flag: `WATCHFILES_FORCE_POLLING=true`
- **Environment Variables**:
  - `ENVIRONMENT=local`
  - `DB_HOST=postgres`, `DB_PORT=5432`, `DB_NAME=report_service_db`
  - `DB_USER=postgres`, `DB_PASSWORD=postgres`
  - `USER_SERVICE_BASE_URL=http://user-service:8001`
  - `OPERATION_SERVICE_BASE_URL=http://operation-service:8002`
  - `JWT_SECRET_KEY=<shared-secret>`
  - `JWT_ALGORITHM=HS256`, `SYNC_PAGE_SIZE=100`, `CORS_ORIGINS=*`
- **Healthcheck**: `curl -f http://localhost:8003/health || exit 1`

### 2.5 API Gateway (`kong`)
- **Base Image**: `kong:3.9-alpine` (pinned version)
- **Mode**: DB-less declarative (`KONG_DATABASE=off`)
- **Host Ports**:
  - Proxy: `127.0.0.1:8000:8000` (loopback only)
  - Admin API: `127.0.0.1:8001:8001` (loopback only, never 0.0.0.0)
- **Volume Mounts**:
  - `./kong/kong.yml:/kong/declarative/kong.yml:ro` (read-only declarative route configuration)
- **Hot Reload / Dynamic Update**: `docker compose -f docker-compose.local.yml exec kong kong reload`
- **Dependencies**: `user-service`, `operation-service`, `report-service`
- **Healthcheck**: `kong health` or `wget -q -O - http://127.0.0.1:8001/status || exit 1`

### 2.6 Frontend Client (`frontend`)
- **Build Context**: `../coffee_shop_frontend`
- **Dockerfile**: Development mode via `node:20-alpine` with `npm run dev`
- **Host Port**: `127.0.0.1:3000:3000` (loopback only)
- **Dependencies**: `kong`
- **Hot Reload**:
  - Bind mount: `../coffee_shop_frontend:/app`
  - Container volume: `/app/node_modules`, `/app/.next` (prevents Windows host file collisions)
  - Polling flag: `WATCHPACK_POLLING=true` (ensures Next.js / webpack detects file modifications on Windows drives)
- **Environment Variables**:
  - `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` (browser client requests through Kong)
  - `INTERNAL_API_BASE_URL=http://kong:8000` (server-side Next.js SSR requests through Kong via Docker network)

---

## 3. Network Isolation & Security Perimeter

```
+--------------------------------------------------------------------------+
|                     WINDOWS HOST (127.0.0.1 Loopback)                    |
|                                                                          |
|   Browser: http://localhost:3000       Admin Tools / DBeaver: 5432        |
|   Kong Proxy Entry: 127.0.0.1:8000     Admin API: 127.0.0.1:8001         |
+--------------------|----------------------------|------------------------+
                     |                            |
                     v                            v
+--------------------------------------------------------------------------+
|                    DOCKER BRIDGE NETWORK: coffee_network                 |
|                                                                          |
|   +--------------------------+          +----------------------------+   |
|   |         frontend         |          |       kong (APIM)          |   |
|   |   (Port 3000 in Docker)  |          |   (Port 8000 / 8001)       |   |
|   +--------------------------+          +-------------+--------------+   |
|                                                       |                  |
|          +--------------------------------------------+                  |
|          |                     |                      |                  |
|          v                     v                      v                  |
|   +--------------+      +--------------+      +---------------+          |
|   | user-service |      |operation-svc |      | report-service|          |
|   | (Port 8001)  |      | (Port 8002)  |      |  (Port 8003)  |          |
|   +-------+------+      +-------+------+      +-------+-------+          |
|           |                     |                     |                  |
|           +---------------------+---------------------+                  |
|                                 |                                        |
|                                 v                                        |
|                     +----------------------+                             |
|                     |       postgres       |                             |
|                     |     (Port 5432)      |                             |
|                     +----------------------+                             |
+--------------------------------------------------------------------------+
```

### Key Architectural Assurances:
1. **Zero Host Bypass**: Backend microservices (`user-service`, `operation-service`, `report-service`) expose ports only inside `coffee_network`. They cannot be reached directly from the host.
2. **Loopback Protection**: All published ports explicitly specify `127.0.0.1` (`127.0.0.1:8000:8000`, `127.0.0.1:8001:8001`, `127.0.0.1:5432:5432`, `127.0.0.1:3000:3000`). No ports bind to `0.0.0.0`, preventing exposure to LAN or public networks.
3. **Dual Next.js Routing**: Client browser calls `http://localhost:8000`; server-side container calls `http://kong:8000`.

# Backend Overview

## Project Purpose

**Coffee Shop Microservices Platform** is a backend for a coffee shop application, built as three independent FastAPI microservices. Each service owns its own PostgreSQL database and communicates with the others only through HTTP and a shared stateless JWT — no service ever reads another service's database directly.

This is a coursework-scale system intentionally designed to demonstrate:
- Microservices architecture with strict data isolation
- Stateless JWT authentication shared across services
- Transactional stock management
- Eventually consistent reporting via HTTP-based data sync

---

## Technology Stack

| Concern | Technology / Library |
|---|---|
| Language | Python 3.14.0 |
| Framework | FastAPI 0.137.1 |
| ASGI Server | Uvicorn 0.49.0 |
| ORM | SQLAlchemy 2.0.51 (sync, legacy `Query` style) |
| Database | PostgreSQL (via `psycopg2-binary 2.9.12`) |
| Data validation | Pydantic 2.13.4 |
| Authentication | PyJWT 2.10.1 |
| Password hashing | bcrypt 4.2.1 |
| HTTP client (sync) | httpx 0.28.1 (used only in report_service sync) |
| Migrations (not active) | Alembic 1.18.4 (installed, not yet wired up) |
| Environment config | python-dotenv 1.2.2 |
| Email validation | email-validator 2.2.0 |
| Dependency management | `pip` + shared `requirements.txt` at repo root |

> [!NOTE]
> Alembic is in `requirements.txt` but **not configured or used** — all three services use `Base.metadata.create_all()` on startup for local development convenience.

---

## Architecture

The project follows a **Microservices architecture with a shared JWT secret**.

```
┌─────────────────────────────────────────────────────────────┐
│  Client (browser / mobile / REST Client)                     │
└──┬──────────────────┬───────────────────┬───────────────────┘
   │                  │                   │
   ▼                  ▼                   ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│ user_service │  │operation_service │  │   report_service     │
│  :8001       │  │  :8002           │  │   :8003              │
│              │  │                  │  │                      │
│ user_service │  │operation_service │  │ report_service_db    │
│ _db          │  │_db               │  │ (*_snapshot tables)  │
└──────────────┘  └──────────────────┘  └──────┬───────────────┘
                                                │  HTTP sync
                                                │  (admin JWT)
                                         ┌──────▼──────────────┐
                                         │ user_service &       │
                                         │ operation_service    │
                                         │ public REST APIs     │
                                         └─────────────────────┘
```

**Communication rules:**
1. **Auth (every request):** Only `user_service` issues JWTs. `operation_service` and `report_service` verify tokens locally using the shared `JWT_SECRET_KEY` — no inter-service network call needed per request.
2. **Data sync (report_service only):** `report_service` mints its own short-lived internal admin JWT and calls `GET /user`, `GET /product`, `GET /order` to populate its local `*_snapshot` tables. This is the **only** inter-service HTTP traffic in the system.

**Architecture within each service:** All three follow an identical **Layered Architecture**:

```
api/ (Router layer)
  └─► services/ (Business logic layer)
        └─► repository/ (Data access layer)
              └─► models/ (Database entity layer)
schemas/      (Pydantic validation & serialization)
core/         (Config, DB engine, Security, Exceptions)
dependencies/ (FastAPI DI: DB session, Auth)
```

---

## Service Inventory

| Service | Port | Database | Entry Point |
|---|---|---|---|
| `user_service` | 8001 | `user_service_db` | `user_service/app/main.py` |
| `operation_service` | 8002 | `operation_service_db` | `operation_service/app/main.py` |
| `report_service` | 8003 | `report_service_db` | `report_service/app/main.py` |

> [!IMPORTANT]
> `operation_service/main.py` and `report_service/main.py` at the **root** of each service folder are **stub files** left from project generation (they do `return {"message": "Hello World"}`). The real entry points are inside `app/main.py`.

---

## Directory Structure

Each service follows an identical layout:

```
<service_name>/
├── app/
│   ├── main.py              # FastAPI app factory, middleware, router wiring
│   ├── api/                 # APIRouter definitions (route handlers only)
│   ├── core/
│   │   ├── config.py        # Settings loaded from .env via os.getenv
│   │   ├── database.py      # SQLAlchemy engine + SessionLocal + Base
│   │   ├── exception.py     # Custom ApplicationError hierarchy
│   │   ├── exception_handler.py  # Global handler → JSON envelope
│   │   └── security.py      # JWT encode/decode; bcrypt (user_service only)
│   ├── dependencies/
│   │   ├── auth.py          # get_current_user, require_roles DI factories
│   │   └── db.py            # get_db generator (yields Session, closes on exit)
│   ├── models/              # SQLAlchemy ORM models (declarative, Mapped style)
│   ├── repository/          # Pure DB access functions (no business logic)
│   ├── schemas/             # Pydantic v2 request/response models
│   │   └── api_response.py  # Generic ApiResponse[T] + PaginatedData[T]
│   └── services/            # Business logic classes
├── .env                     # Active env (not committed)
├── .env.example             # Template for all required env variables
└── test_main.http           # VS Code / PyCharm REST Client walk-through
```

---

## Application Startup

**All three services follow the same startup sequence:**

1. `Base.metadata.create_all(bind=engine)` — creates missing tables (auto-schema for local dev).
2. FastAPI app is instantiated with title and metadata.
3. `CORSMiddleware` is added with origins from `CORS_ORIGINS`.
4. APIRouters are included.
5. `ApplicationError` global exception handler is registered.

**report_service additionally:**
6. `@app.on_event("startup")` fires `SyncService().sync_all(db)` — best-effort pull from other services. If they are unreachable, the exception is caught and logged; the app still starts.

**Run commands:**

```bash
# Terminal 1 — start first
cd user_service && uvicorn app.main:app --reload --port 8001

# Terminal 2
cd operation_service && uvicorn app.main:app --reload --port 8002

# Terminal 3 — start last (sync on startup needs the other two)
cd report_service && uvicorn app.main:app --reload --port 8003
```

Swagger UI is available at `/docs` on each port. OpenAPI JSON at `/openapi.json`.

---

## Standard Response Envelope

Every endpoint in all three services returns the same JSON structure:

```json
{
  "success": true,
  "error_code": null,
  "message": "Human-readable status message",
  "data": { ... }
}
```

Error responses:
```json
{
  "success": false,
  "error_code": "err_404",
  "message": "User with id 99 not found",
  "data": null
}
```

Paginated responses wrap data in:
```json
{
  "success": true,
  "message": "...",
  "data": {
    "items": [ ... ],
    "meta": {
      "page": 1,
      "page_size": 20,
      "total_items": 53,
      "total_pages": 3
    }
  }
}
```

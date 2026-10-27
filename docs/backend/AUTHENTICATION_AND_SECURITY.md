# Authentication and Security

## Authentication Architecture

The system uses a **shared-secret, stateless JWT** pattern:

- **Only `user_service`** issues JWTs (at `POST /user/login`).
- **`operation_service` and `report_service`** verify JWTs locally using the same `JWT_SECRET_KEY` — no network call back to `user_service` per request.
- **`report_service`** additionally mints its own short-lived internal "service account" JWT to authenticate outbound sync HTTP calls.

---

## JWT Configuration

| Setting | Variable | Default |
|---|---|---|
| Algorithm | `JWT_ALGORITHM` | `HS256` |
| Access token expiry | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` (1 hour) |
| Service token expiry (report_service only) | `SERVICE_TOKEN_EXPIRE_MINUTES` | `5` |
| Secret key | `JWT_SECRET_KEY` | `"change-me-in-production"` ⚠️ |

> [!CAUTION]
> The default `JWT_SECRET_KEY` is `"change-me-in-production"`. If `.env` is not configured before deployment, all services will accept tokens signed with this well-known default — a critical security vulnerability.

### JWT Payload Structure (user tokens)

```json
{
  "sub": "1",
  "email": "alice@example.com",
  "role": "customer",
  "iat": 1727800000,
  "exp": 1727803600
}
```

### JWT Payload Structure (internal service tokens — report_service)

```json
{
  "sub": "report_service",
  "email": "sync@report-service.internal",
  "role": "admin",
  "iat": 1727800000,
  "exp": 1727800300
}
```

---

## Authentication Flow (user_service)

```
1. Client → POST /user/login { email, password }
2. user_service:
   a. user_repo.get_by_email(db, email) — finds user (soft-delete aware)
   b. security.verify_password(plain, hashed) — bcrypt.checkpw
   c. Check user.is_active
   d. security.create_access_token({ sub: str(user.id), email, role })
      → jwt.encode(claims + iat/exp, JWT_SECRET_KEY, HS256)
3. Response: { access_token: "<JWT>", token_type: "bearer", expires_in_minutes: 60, user: {...} }
```

---

## Token Verification Flow (operation_service / report_service)

```
1. Client → Any protected endpoint (Authorization: Bearer <JWT>)
2. FastAPI: HTTPBearer(auto_error=False) extracts credentials
3. dependencies/auth.get_current_user:
   a. Checks credentials is not None
   b. security.decode_access_token(token)
      → jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
      → raises TokenExpired on ExpiredSignatureError
      → raises InvalidToken on other InvalidTokenError
   c. Extracts "sub", "email", "role" claims
   d. For user_service: if sub is numeric, queries DB for User by id;
      checks is_active; handles internal service accounts (non-numeric sub)
      For operation_service / report_service: constructs CurrentUser(id, email, role)
      purely from JWT claims — no DB lookup
4. Returns User / CurrentUser to route handler
```

---

## Password Security

**Library:** `bcrypt 4.2.1`

| Aspect | Implementation |
|---|---|
| Hashing | `bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt())` |
| Verification | `bcrypt.checkpw(plain.encode()[:72], stored_hash.encode())` |
| 72-byte guard | Input is explicitly truncated to 72 bytes before bcrypt (bcrypt's native limit) |
| Error handling | `ValueError`, `TypeError` caught in `verify_password` (handles malformed legacy hashes) |
| Storage | Stored as UTF-8 string in `users.password` column |

> [!TIP]
> The bcrypt guard against the 72-byte truncation is explicitly implemented and commented — this is a good security practice.

---

## Authorization

### Dependency Factories

All three services implement identical `require_roles(*allowed_roles)` and `get_current_user` patterns in `dependencies/auth.py`.

#### `get_current_user`

Returns the authenticated user/principal. Raises `Unauthorized` (401) if token is missing, invalid, or expired.

**user_service special handling:** Also performs a DB lookup to verify the user still exists and is active. Handles internal service-account tokens (non-numeric `sub`) by returning a synthetic `User(id=-1)`.

**operation_service / report_service:** Returns `CurrentUser(id, email, role)` from JWT claims only — no DB lookup. Role changes take effect only after the token expires.

#### `require_roles(*allowed_roles)`

Dependency factory that returns a checker function. Raises `Forbidden` (403) if `current_user.role not in allowed_roles`.

#### `require_self_or_roles` (user_service only)

Present in `user_service/app/dependencies/auth.py` but **not actually used** by any router — all self-or-role checks are done inline in the router functions directly.

---

## Role-Permission Matrix

| Feature | customer | staff | admin |
|---|---|---|---|
| Register | ✅ (own account) | ✅ | ✅ |
| Login | ✅ | ✅ | ✅ |
| View own profile | ✅ | ✅ | ✅ |
| View user list | ❌ | ✅ | ✅ |
| View other user's profile | ❌ | ✅ | ✅ |
| Update own profile | ✅ | ✅ | ✅ |
| Update other user's profile | ❌ | ❌ | ✅ |
| Change own password | ✅ | ✅ | ✅ |
| Promote/demote role | ❌ | ❌ | ✅ |
| Delete user | ❌ | ❌ | ✅ |
| Browse products (menu) | ✅ (public) | ✅ | ✅ |
| Get single product | ✅ (public) | ✅ | ✅ |
| Add product | ❌ | ✅ | ✅ |
| Update product | ❌ | ✅ | ✅ |
| Adjust stock | ❌ | ✅ | ✅ |
| Deactivate product | ❌ | ✅ | ✅ |
| Create order | ✅ | ✅ | ✅ |
| View own orders | ✅ | ✅ | ✅ |
| View all orders | ❌ | ✅ | ✅ |
| Cancel own order | ✅ | ✅ | ✅ |
| Update order status | ❌ | ✅ | ✅ |
| Pay own order | ✅ | ✅ | ✅ |
| View own payment | ✅ | ✅ | ✅ |
| All report endpoints | ❌ | ✅ | ✅ |
| Trigger sync | ❌ | ✅ | ✅ |

---

## CORS Configuration

All three services add `CORSMiddleware`:

```python
allow_origins=settings.CORS_ORIGINS   # from CORS_ORIGINS env var
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

Default: `CORS_ORIGINS=*` (all origins allowed) in `.env.example`.

> [!WARNING]
> `allow_origins=["*"]` combined with `allow_credentials=True` is **technically disallowed by browsers** (CORS spec) and FastAPI will raise a warning. In practice, setting `CORS_ORIGINS=*` in production is insecure — it should be restricted to trusted frontend origins.

---

## Security Review

### Confirmed Vulnerabilities / Issues

| # | Severity | Issue | Location | Impact |
|---|---|---|---|---|
| 1 | 🔴 Critical | Default `JWT_SECRET_KEY="change-me-in-production"` | All `.env` configs | If env file is missing or not set, all services accept tokens signed with the public default key |
| 2 | 🟠 High | Stale JWT claims after role/account changes | All services | A deactivated user's existing token is still valid until expiry (1 hour by default). In user_service this is caught by the DB lookup; in operation_service and report_service it is not. |
| 3 | 🟠 High | `CORS_ORIGINS=*` + `allow_credentials=True` | All `main.py` files | Violates browser CORS spec; should use specific origins in production |
| 4 | 🟡 Medium | No refresh token mechanism | All services | Only access tokens; once expired, users must log in again. No ability to silently renew sessions. |
| 5 | 🟡 Medium | No token blacklisting / logout endpoint | All services | JWT cannot be revoked after issuance; logout is client-side only |
| 6 | 🟡 Medium | Internal service token has `role="admin"` | `report_service/core/security.py` | Service token grants admin access to all staff/admin-protected endpoints; compromise of `JWT_SECRET_KEY` allows minting arbitrary admin tokens |
| 7 | 🟡 Medium | `require_self_or_roles` defined but unused | `user_service/dependencies/auth.py` | Authorization logic is duplicated inline in router handlers instead of using this reusable dependency |

### Potential Risks (not confirmed vulnerabilities)

| # | Issue | Explanation |
|---|---|---|
| 1 | Error message verbosity | `UserNotFound(user_id)` includes the ID in the message — acceptable in most contexts but could aid enumeration |
| 2 | `InvalidCredentials` returns same message for wrong email and wrong password | This is good practice (prevents email enumeration) ✅ |
| 3 | No rate limiting | Brute-force login attempts on `POST /user/login` are not throttled |
| 4 | No HTTP security headers | No `Strict-Transport-Security`, `X-Frame-Options`, etc. (ASGI middleware not configured) |
| 5 | `datetime.now()` (naive) in JWT `iat`/`exp` claims | `security.py` in `user_service` uses `datetime.now(timezone.utc)` correctly; this is fine ✅ |

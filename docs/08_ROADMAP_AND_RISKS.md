# Deliverables 7 & 8: Prioritized Implementation Roadmap & Risk Register (`docs/08_ROADMAP_AND_RISKS.md`)

---

## 1. Prioritized Implementation Roadmap (Phases 1 / 2 / 3)

### Phase 1: Core Bakong KHQR Foundation & Critical Bug Fixes (`[MUST]` — Completed in Branch `feature/bakong-khqr`)
| Task | Priority | Effort Estimate | Status |
| :--- | :--- | :--- | :--- |
| **1.1** Database schema design & Alembic migration (`0001_bakong_khqr_schema.py`) for `payments`, `payment_attempts`, `payment_events`, `refunds`, `idempotency_keys`, and `verification_jobs`. | **`[MUST]`** | **4 hours** | **Done** |
| **1.2** EMVCo Dynamic KHQR TLV generator (`Tag 29`/`30`, `Tag 53` USD/KHR, `Tag 54` amount, `Tag 62` bill reference, `Tag 99` timestamps, `Tag 63` CRC16-CCITT) + MD5 hash computation (`bakong_khqr.py`). | **`[MUST]`** | **6 hours** | **Done** |
| **1.3** NBC Bakong Open API v1 client (`check_transaction_by_md5`, `check_transaction_by_md5_list`, `renew_token`, `generate_deeplink_by_qr`) + PostgreSQL `FOR UPDATE SKIP LOCKED` verification worker & reconciler. | **`[MUST]`** | **8 hours** | **Done** |
| **1.4** FastAPI endpoints (`POST /order/{id}/payment`, `GET /order/{id}/payment`, `/verify`, `/regenerate`, `/cancel`, `/refund`) + 10 pytest unit/worker/respx test cases. | **`[MUST]`** | **6 hours** | **Done** |
| **1.5** Critical frontend fixes: Cart customization price calculation fix (`customer-add-to-cart.tsx`), Bakong KHQR `PayDialog` with countdown + 3s polling + regeneration, Order Detail customization display, Category filter on `/products`, and ESLint cleanup. | **`[MUST]`** | **6 hours** | **Done** |
| **Phase 1 Total** | | **~30 hours (3.5–4 dev days)** | **100% Complete** |

---

### Phase 2: Production Hardening, Dedicated Worker Process & E2E Automation (`[SHOULD]`)
| Task | Priority | Effort Estimate | Description |
| :--- | :--- | :--- | :--- |
| **2.1** Standalone background worker runner (`python -m app.worker`) executing `PaymentVerificationWorker.process_due_jobs()` every 2 seconds and `reconcile_expired_payments()` every 60 seconds under systemd / Docker Compose. | **`[MUST]`** (before prod traffic) | **4 hours** | Decouples background Bakong polling from FastAPI web worker processes. |
| **2.2** Cambodian Egress IP / Hosting Setup & NBC SIT-to-Production Onboarding. | **`[MUST]`** (before prod traffic) | **4–8 hours** (+ NBC KYC wait) | Provision Cambodia VPS or static NAT IP whitelisted with NBC (`api-bakong.nbc.gov.kh`). |
| **2.3** Render actual graphical 2D QR matrix SVG in `PayDialog` (using lightweight client SVG encoder or server-generated SVG data URI) and add `<Suspense>` wrappers around `Navbar`/`ProductsPage`. | **`[SHOULD]`** | **3 hours** | Allows physical phone camera scanning directly off the screen in addition to deeplinks. |
| **2.4** Vitest + React Testing Library & Playwright E2E test runner integration in `coffee_shop_frontend/package.json`. | **`[SHOULD]`** | **6 hours** | Automates browser checkout verification in GitHub Actions. |
| **2.5** Cleanup commit (`cleanup: remove unused stubs and legacy artifacts`) for items approved from `docs/04_CLEANUP_REPORT.md`. | **`[SHOULD]`** | **1 hour** | Removes dead `export {};` hook stubs and stale `.db` files in a dedicated revertible commit. |
| **Phase 2 Total** | | **~18–22 hours (2.5 dev days)** | |

---

### Phase 3: Scale, Observability & Bilingual UX Enhancements (`[NICE-TO-HAVE]`)
| Task | Priority | Effort Estimate | Description |
| :--- | :--- | :--- | :--- |
| **3.1** Extract `payment-service` into a separate deployable container (`:8004`) with its own `payment_service_db` and PostgreSQL `LISTEN/NOTIFY` SSE stream to the frontend. | **`[NICE-TO-HAVE]`** | **12 hours** | Replaces 3-second client polling with instant Server-Sent Events pushed on `NOTIFY payment_events_channel`. |
| **3.2** Bilingual Localization (`next-intl` for Khmer `km-KH` + English `en-US`) with dual USD/KHR price display on menu cards. | **`[NICE-TO-HAVE]`** | **10 hours** | Meets Cambodian retail POS best practices (displaying both `$` and `៛`). |
| **3.3** `HttpOnly; Secure; SameSite=Strict` cookie auth via Next.js BFF proxy and automated Prometheus/Telegram alerting when `BAKONG_TOKEN` is `< 7 days` from expiry. | **`[NICE-TO-HAVE]`** | **8 hours** | Hardens browser token security and operational monitoring. |
| **Phase 3 Total** | | **~30 hours (4 dev days)** | |

---

## 2. Risk Register & Mitigations

| Risk ID | Risk Description | Likelihood | Impact | Mitigation Applied |
| :--- | :--- | :--- | :--- | :--- |
| **R-01** | **NBC Bakong Geo-IP Blocking**: Production API (`https://api-bakong.nbc.gov.kh`) drops requests from non-Cambodian cloud regions (AWS/GCP/Render). | **High** | **Critical** | Documented in `docs/02_BAKONG_DESIGN.md`; `BAKONG_API_BASE_URL` supports either direct Cambodian hosting or a Cambodian reverse proxy, and `respx`/SIT URL is used for testing. |
| **R-02** | **Bakong Open API Lacks Webhooks**: Relying on client redirect alone loses payments if the customer closes their browser tab after paying in the Bakong/ABA app. | **High** | **Critical** | Mitigated via PostgreSQL `FOR UPDATE SKIP LOCKED` background worker (`verification_jobs`) + 30-minute `reconcile_expired_payments()` job that recovers late/abandoned browser sessions server-side. |
| **R-03** | **Bakong Access Token Expiry**: NBC JWT token expires (30–90 days), causing all `check_transaction_by_md5` calls to return HTTP 401 or `errorCode=6`. | **Medium** | **High** | Implemented automatic reactive token renewal in `BakongOpenAPIClient.check_transaction_by_md5()` (`POST /v1/renew_token` using `BAKONG_REGISTERED_EMAIL`) tested in `test_worker_handles_bakong_timeout_and_token_auto_renewal`. |
| **R-04** | **Customer Pays After QR Expiry & Order Cancellation**: Customer scans QR at `02:58`, order is cancelled/restocked at `03:05`, and customer confirms transfer in bank app at `03:10`. | **Medium** | **High** | Reconciler detects `order.status == 'cancelled'`, transitions payment to `refund_required`, creates a `pending_manual` row in `refunds`, and logs `payment.conflict_refund_required` for staff resolution. |
| **R-05** | **KHR Decimal Rejections**: Sending fractional decimals (`18000.50`) for KHR (`ISO 116`) causes mobile banking apps to reject the KHQR scan. | **Medium** | **High** | `format_khqr_amount()` and `convert_usd_to_khr()` strictly enforce integer-only KHR values (`ROUND_HALF_UP` to whole Riel) and reject fractional KHR at generation time. |
| **R-06** | **Double Order Progression Under Race Conditions**: Customer clicks "I Have Paid — Check Status" at the exact instant the background worker verifies the same MD5. | **Medium** | **Medium** | Both paths acquire a PostgreSQL row lock (`SELECT ... FROM payments WHERE id = :id FOR UPDATE`) and check `if payment.status in ('paid', 'success'): return` idempotently. |

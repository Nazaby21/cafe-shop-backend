# Open Questions, Official Spec Discrepancies & Architectural Assumptions (`docs/OPEN_QUESTIONS.md`)

> Per unattended execution rules, every question or discrepancy between common payment gateway assumptions and the **official NBC Bakong Open API & KHQR specification** is documented here along with the engineering assumption applied.

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
- **Question for Project Owner**: Where will your production backend be hosted?
- **Assumption & Design Decision**: We made `BAKONG_API_BASE_URL` configurable (`https://sit-api-bakong.nbc.gov.kh` for SIT, `https://api-bakong.nbc.gov.kh` for Cambodia-hosted production, or an authorized Cambodian reverse proxy URL) and added a `BAKONG_MOCK_MODE` (`true` in local/test) so development and CI never call the live production API.

---

## 2. Project-Specific Architectural Questions & Assumptions

### Q4: Dedicated `payment-service` vs Existing `operation_service` Payment Routes
- **Observation**: Currently, the frontend's `operationClient` (`NEXT_PUBLIC_OPERATION_API_URL`, port `8002`) calls `POST /order/{id}/payment` and `GET /order/{id}/payment` directly on `operation_service`, and existing integration tests (`coffee_shop/tests/test_cross_service_integration.py` and `operation_service/tests/test_operation_api.py`) test `operation_service`.
- **Question**: Should Bakong KHQR endpoints also be served on `operation_service` (`/order/{order_id}/payment/*`) so the existing frontend `operationClient` works without requiring a 4th port in `.env.local`, or only on a standalone `payment_service` (`:8004`)?
- **Assumption & Design Decision**: We provide **both**:
  1. Full Bakong KHQR generation, CRC16/MD5, verification worker (`SKIP LOCKED`), Alembic migrations, and endpoints integrated into `operation_service` (preserving 100% compatibility with `NEXT_PUBLIC_OPERATION_API_URL` and existing service topology), **AND**
  2. Clean modular separation (`BakongKHQRService`, `BakongOpenAPIClient`, `PaymentVerificationWorker`) that can run either as a standalone `payment-service` microservice (`:8004`) or embedded inside `operation_service` (`:8002`).

### Q5: Settlement Currency (USD vs KHR) and Exchange Rate
- **Observation**: All product prices in `operation_service_db.products` are stored in `USD` (e.g., `$3.50`). In Cambodia, customers frequently pay KHQR from either their USD or KHR bank account (Bakong automatically handles cross-currency settlement at the acquiring bank's rate if the QR is in USD, or merchants can display a USD or KHR QR).
- **Question**: What store exchange rate should be used when a customer explicitly requests a KHR-denominated KHQR?
- **Assumption & Design Decision**: Default KHQR currency is `USD` (matching `orders.total_amount`). When `currency="KHR"` is requested, we convert using configurable `BAKONG_USD_TO_KHR_RATE` (default `4100` KHR per `1.00 USD`, rounded to integer KHR with 0 decimal places as required by EMVCo Tag `54` for ISO `116`).

### Q6: Staff Offline Cash Payments vs "ONLY Bakong KHQR"
- **Observation**: The prompt states *"Integrate the Bakong KHQR payment gateway (ONLY Bakong KHQR, no ABA PayWay or other gateways)"*, while existing commit `1e665cf` tests staff marking orders paid.
- **Assumption & Design Decision**: All third-party online card/wallet gateways (`card`, `e_wallet`, ABA PayWay, Stripe, etc.) are removed/excluded. Online checkout uses **exclusively Bakong KHQR** (`method="khqr"`). Staff/admin can still advance orders via `PATCH /order/{id}/status` as required by existing integration tests.

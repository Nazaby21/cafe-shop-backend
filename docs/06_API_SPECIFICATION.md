# Deliverable 3: Bakong KHQR Payment API Specification (`docs/06_API_SPECIFICATION.md`)

> Implemented in [`coffee_shop/operation_service/app/api/payment_route.py`](file:///D:/Study/Year-4/Python/coffee_shop/operation_service/app/api/payment_route.py) and [`coffee_shop/operation_service/app/schemas/payment_schema.py`](file:///D:/Study/Year-4/Python/coffee_shop/operation_service/app/schemas/payment_schema.py). All endpoints use JWT Bearer authentication (`Authorization: Bearer <token>`) and return the uniform `ApiResponse[T]` envelope.

---

## 1. OpenAPI 3.1 Specification Summary

### 1.1 `POST /order/{order_id}/payment` — Initiate / Fetch Active Bakong KHQR Payment
- **Auth**: Authenticated order owner (`customer`), `staff`, or `admin`.
- **Idempotency**: If an unexpired `pending` KHQR attempt with the same `currency` already exists for `order_id`, returns the existing QR and MD5 without creating a duplicate attempt.
- **Request Body (`CreatePaymentRequest`)**:
  ```json
  {
    "method": "khqr",
    "currency": "USD",
    "idempotency_key": "550e8400-e29b-41d4-a716-446655440000"
  }
  ```
- **Response `200 OK` (`ApiResponse[PaymentResponse]`)**:
  ```json
  {
    "success": true,
    "error_code": null,
    "message": "Bakong KHQR generated; awaiting customer scan",
    "data": {
      "id": 1,
      "order_id": 42,
      "amount": "9.00",
      "currency": "USD",
      "method": "khqr",
      "status": "pending",
      "transaction_ref": "ORD-42-A1",
      "failure_reason": null,
      "qr_string": "00020101021229190015coffeeshop@aclb52045814530384054049.005802KH5911Coffee Shop6010Phnom Penh62380109ORD-42-A10315CoffeeShop-Main0706POS-01993400131762000000000011317620001800006304A1B2",
      "qr_md5": "d60f3db96913029a2af979a1662c1e72",
      "deeplink_url": "https://bakong.page.link/...",
      "expires_at": "2026-11-02T20:48:00",
      "paid_at": null,
      "bakong_transaction_hash": null,
      "payer_account_masked": null,
      "attempt_count": 1,
      "created_at": "2026-11-02T20:45:00",
      "updated_at": "2026-11-02T20:45:00"
    }
  }
  ```
- **Error Responses**:
  - `403 Forbidden` (`err_403`): Caller is neither the order owner nor staff/admin.
  - `404 Not Found` (`err_404_order`): Order does not exist.
  - `409 Conflict` (`err_409_order_not_payable`): Order status is not `pending`.
  - `409 Conflict` (`err_409_payment_exists`): Order is already `paid`.
  - `503 Service Unavailable` (`err_503_payment_gateway_unavailable`): `BAKONG_ACCOUNT_ID` is not configured.

---

### 1.2 `GET /order/{order_id}/payment` — Get Payment Status & QR Metadata
- **Auth**: Order owner, `staff`, or `admin`.
- **Behavior**: Returns the current `PaymentResponse`. Automatically transitions `pending -> expired` if `NOW() >= expires_at`.
- **Response `200 OK`**: Same schema as `ApiResponse[PaymentResponse]`.
- **Error Responses**: `404 Not Found` (`err_404_payment`) if no payment attempt has been initiated yet.

---

### 1.3 `POST /order/{order_id}/payment/verify` — Trigger Live Bakong MD5 Verification
- **Auth**: Order owner, `staff`, or `admin`.
- **Behavior**: Acquires a `FOR UPDATE SKIP LOCKED` lock on the verification job and queries `POST /v1/check_transaction_by_md5` on the NBC Bakong Open API. Validates receiver account (`toAccountId`), currency, and amount server-side. If verified (`responseCode == 0`), atomically updates `payments.status = 'paid'` and `orders.status = 'paid'`.
- **Response `200 OK`**:
  ```json
  {
    "success": true,
    "error_code": null,
    "message": "Payment verification completed",
    "data": {
      "id": 1,
      "order_id": 42,
      "amount": "9.00",
      "currency": "USD",
      "method": "khqr",
      "status": "paid",
      "transaction_ref": "bakong_tx_hash_9001",
      "failure_reason": null,
      "qr_string": "000201010212...",
      "qr_md5": "d60f3db96913029a2af979a1662c1e72",
      "deeplink_url": null,
      "expires_at": "2026-11-02T20:48:00",
      "paid_at": "2026-11-02T20:46:12",
      "bakong_transaction_hash": "bakong_tx_hash_9001",
      "payer_account_masked": "cu***an@aba",
      "attempt_count": 1
    }
  }
  ```

---

### 1.4 `POST /order/{order_id}/payment/regenerate` — Regenerate Expired/Failed KHQR
- **Auth**: Order owner, `staff`, or `admin`.
- **Request Body (`CreatePaymentRequest`, optional)**:
  ```json
  {
    "method": "khqr",
    "currency": "KHR"
  }
  ```
- **Behavior**: Marks any prior pending attempt as `expired`, increments `attempt_count`, generates a new bill number (`ORD-{order_id}-A{attempt_count}`), new dynamic KHQR string, new `qr_md5`, new 180s `expires_at`, and enqueues a new `VerificationJob`.

---

### 1.5 `POST /order/{order_id}/payment/cancel` — Cancel Pending Payment
- **Auth**: Order owner, `staff`, or `admin`.
- **Behavior**: Transitions a `pending` or `expired` payment to `cancelled`, dequeues its `VerificationJob`, and appends a `payment.cancelled` event.

---

### 1.6 `POST /order/{order_id}/payment/refund` — Record Manual Bakong Refund
- **Auth**: `staff` or `admin` only (`require_roles("admin", "staff")`).
- **Request Body (`RefundPaymentRequest`)**:
  ```json
  {
    "amount": "9.00",
    "reason": "Customer requested cancellation after payment; refunded via Bakong app",
    "external_refund_ref": "BAKONG-REF-20261102-001"
  }
  ```
- **Behavior**: Transitions `paid` or `refund_required` payment to `refunded`, inserts a `completed` row in `refunds`, and records `payment.refunded` in `payment_events` with `actor="staff:<id>"`.

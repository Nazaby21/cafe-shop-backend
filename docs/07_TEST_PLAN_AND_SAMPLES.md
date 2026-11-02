# Step 5 & Deliverable 6: Testing Strategy, Test Matrix & Implementation (`docs/07_TEST_PLAN_AND_SAMPLES.md`)

> **Executed Backend Test Results**:
> - `user_service`: **5 passed** (`1.17s`)
> - `operation_service` (including new [`tests/test_bakong_khqr.py`](file:///D:/Study/Year-4/Python/coffee_shop/operation_service/tests/test_bakong_khqr.py)): **13 passed** (`1.61s`)
> - `report_service`: **4 passed** (`0.87s`)
> - `tests/test_cross_service_integration.py`: **1 passed** (`2.71s`)
> - **Total**: **23 / 23 tests passing (100%)**, `ruff check .` clean, `scripts/check_mock_patterns.py` clean, `tsc --noEmit` 0 errors.

---

## 1. Test Case Matrix (Feature, Scenario, Expected Result, Priority)

| ID | Feature / Layer | Scenario | Expected Result | Priority | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | KHQR Generator (Unit) | Generate dynamic USD KHQR (`$4.50`, `ORD-42-A1`) | Produces valid EMVCo TLV string (`Tag 01=12`, `Tag 29`, `Tag 53=840`, `Tag 54=4.50`, `Tag 99` timestamps, `Tag 63` CRC16-CCITT valid) + 32-char hex MD5. | **`[MUST]`** | **Implemented & Passing** (`test_khqr_generation_and_crc16_verification`) |
| **TC-02** | KHQR CRC16-CCITT (Unit) | Tamper with 1 character of generated KHQR payload | `verify_khqr_crc()` returns `False`. | **`[MUST]`** | **Implemented & Passing** (`test_khqr_generation_and_crc16_verification`) |
| **TC-03** | Corporate KHQR & KHR (Unit) | Generate corporate Tag 30 KHQR in `KHR` (`18000`) | Uses `Tag 30` (`merchant_id` + `acquiring_bank`), `Tag 53=116`, `Tag 54=18000` (integer). | **`[MUST]`** | **Implemented & Passing** (`test_khqr_corporate_merchant_tag_30`) |
| **TC-04** | Amount & Currency Validation (Unit) | Pass `<= 0` amount, fractional `KHR` (`18000.50`), `>2` decimal `USD` (`4.559`), or unsupported currency (`EUR`) | Raises `BakongAmountValidationError` (`HTTP 400`). | **`[MUST]`** | **Implemented & Passing** (`test_khqr_amount_and_currency_validation`) |
| **TC-05** | Payment State Machine (Unit) | Verify allowed & forbidden transitions (`pending -> paid/expired/cancelled`, `expired -> paid/refund_required`, `paid -> refunded`, `cancelled -> paid` blocked) | `PaymentStatus.can_transition()` allows valid forward transitions and blocks terminal reversals. | **`[MUST]`** | **Implemented & Passing** (`test_payment_state_machine_and_account_masking`) |
| **TC-06** | Create KHQR & Idempotency (Integration) | Call `POST /order/{id}/payment` twice for same pending order | Second call returns the exact same active `payment_id`, `qr_string`, and `qr_md5` with `attempt_count=1`. | **`[MUST]`** | **Implemented & Passing** (`test_khqr_payment_creation_idempotency_and_verification_success`) |
| **TC-07** | Verification Worker: `pending -> paid` | Mock Bakong `POST /v1/check_transaction_by_md5` returning `responseCode=0` with matching receiver, currency, and amount | `Payment` transitions to `paid`, `Order` transitions to `paid`, `payer_account_masked` masks PII (`cu***an@aba`), `PaymentEvent('payment.paid')` logged. | **`[MUST]`** | **Implemented & Passing** (`test_khqr_payment_creation_idempotency_and_verification_success`) |
| **TC-08** | Verification Worker: `pending -> expired` + Regenerate QR | QR `expires_at` passes while Bakong returns `responseCode=1, errorCode=1`; customer calls `POST /order/{id}/payment/regenerate` | Worker marks payment `expired`; regenerate endpoint issues `Attempt #2` with new `qr_md5` and resets status to `pending`. | **`[MUST]`** | **Implemented & Passing** (`test_worker_handles_expired_qr_and_regeneration`) |
| **TC-09** | Verification Worker: Bakong Timeout & Token Auto-Renewal | 1) Bakong times out (`httpx.ReadTimeout`); 2) Bakong returns `errorCode=6` (token expired) | 1) Job stays `queued` with backoff; 2) Client calls `POST /v1/renew_token`, rotates JWT, retries MD5 check, and marks payment `paid`. | **`[MUST]`** | **Implemented & Passing** (`test_worker_handles_bakong_timeout_and_token_auto_renewal`) |
| **TC-10** | Edge Cases: Underpayment & Late Payment on Cancelled Order | 1) Customer pays `$3.00` on `$6.00` order; 2) Customer pays after order was cancelled | 1) Payment marked `failed` (`Underpaid`), `Refund` row created; 2) Reconciler marks payment `refund_required` and creates `Refund` row (`late_payment_on_cancelled_order`). | **`[MUST]`** | **Implemented & Passing** (`test_underpayment_overpayment_and_late_payment_reconciliation`) |
| **TC-11** | Manual Refund & Bulk MD5 Check | Staff calls `POST /order/{id}/payment/refund`; worker calls `POST /v1/check_transaction_by_md5_list` | Payment moves `paid -> refunded`, `Refund` completed, `payment.refunded` event logged; batch MD5 response parsed accurately. | **`[MUST]`** | **Implemented & Passing** (`test_staff_manual_refund_and_bulk_md5_list`) |
| **TC-12** | Frontend Cart Price Calculation (Unit / RTL) | Customer selects product (`$3.50`) + customization (`Oat Milk +$0.75`) | `cartStore` item `unitPrice` equals `"4.25"` and `CartDialog` total equals `$4.25 * qty`. | **`[MUST]`** | Fixed in [`customer-add-to-cart.tsx`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/features/product/components/customer-add-to-cart.tsx) |
| **TC-13** | Frontend E2E Checkout Flow (Playwright) | Create order -> Show Bakong KHQR modal with countdown -> Mock paid -> Redirect/show Paid status; plus Expired -> Regenerate QR | Full customer checkout completes without console errors or leaked polling intervals. | **`[SHOULD]`** | Sample Playwright spec provided below |

---

## 2. Coverage Targets (`[MUST]`)

| Component / Module | Target Line Coverage | Target Branch Coverage |
| :--- | :--- | :--- |
| `operation_service/app/services/bakong_khqr.py` | **>= 85%** | **>= 80%** |
| `operation_service/app/services/payment_service.py` | **>= 85%** | **>= 80%** |
| `operation_service/app/api/payment_route.py` | **>= 85%** | **>= 80%** |
| Overall Backend (`user_service`, `operation_service`, `report_service`) | **>= 80%** | **>= 75%** |
| Frontend `src/features/payment/*` & `src/store/cartStore.ts` | **>= 80%** | **>= 75%** |

---

## 3. PostgreSQL Testcontainers Concurrent `SKIP LOCKED` Test Sample (`[SHOULD]`)

When running in CI with Docker available, use the following PostgreSQL integration test to verify that two concurrent `PaymentVerificationWorker` instances never double-process the same `VerificationJob`:

```python
# tests/test_postgres_skip_locked_concurrency.py
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.payment import VerificationJob

@pytest.mark.skipif(not os.getenv("POSTGRES_TEST_URL"), reason="Requires real PostgreSQL for SKIP LOCKED")
def test_concurrent_workers_skip_locked():
    pg_engine = create_engine(os.environ["POSTGRES_TEST_URL"])
    Session = sessionmaker(bind=pg_engine)

    s1 = Session()
    s2 = Session()
    try:
        # Worker 1 locks 1 queued job inside an open transaction
        job_w1 = (
            s1.query(VerificationJob)
            .filter(VerificationJob.status == "queued")
            .with_for_update(skip_locked=True)
            .first()
        )
        assert job_w1 is not None

        # Worker 2 queries concurrently with SKIP LOCKED and must NOT receive job_w1
        job_w2 = (
            s2.query(VerificationJob)
            .filter(VerificationJob.status == "queued")
            .with_for_update(skip_locked=True)
            .first()
        )
        assert job_w2 is None or job_w2.id != job_w1.id
    finally:
        s1.rollback()
        s2.rollback()
        s1.close()
        s2.close()
```

---

## 4. Frontend Unit Test (Vitest + React Testing Library) & Playwright E2E Samples

### 4.1 Vitest Unit Test: `PayDialog` & `cartStore` (`src/features/payment/__tests__/pay-dialog.test.tsx`)
```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import { PayDialog } from '@/features/payment/components/pay-dialog';
import * as paymentApi from '@/features/payment/api';

vi.mock('@/features/payment/api');

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('PayDialog (Bakong KHQR)', () => {
  it('renders KHQR code, MD5, and countdown when payment is pending', async () => {
    vi.mocked(paymentApi.getPayment).mockResolvedValue({
      id: 1,
      order_id: 42,
      amount: '4.50',
      currency: 'USD',
      method: 'khqr',
      status: 'pending',
      transaction_ref: 'ORD-42-A1',
      failure_reason: null,
      qr_string: '00020101021229190015coffeeshop@aclb6304ABCD',
      qr_md5: 'd60f3db96913029a2af979a1662c1e72',
      expires_at: new Date(Date.now() + 120_000).toISOString(),
    });

    renderWithQuery(
      <PayDialog orderId={42} totalAmount="4.50" open={true} onOpenChange={() => {}} />,
    );

    await waitFor(() => {
      expect(screen.getByText(/KHQR • BAKONG/i)).toBeDefined();
    });
    expect(screen.getByText(/d60f3db96913029a2af979a1662c1e72/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /I Have Paid — Check Status/i })).toBeDefined();
  });

  it('shows Regenerate KHQR button when QR is expired', async () => {
    vi.mocked(paymentApi.getPayment).mockResolvedValue({
      id: 1,
      order_id: 42,
      amount: '4.50',
      currency: 'USD',
      method: 'khqr',
      status: 'expired',
      transaction_ref: 'ORD-42-A1',
      failure_reason: null,
      qr_string: '00020101021229190015coffeeshop@aclb6304ABCD',
      qr_md5: 'd60f3db96913029a2af979a1662c1e72',
      expires_at: new Date(Date.now() - 10_000).toISOString(),
    });

    renderWithQuery(
      <PayDialog orderId={42} totalAmount="4.50" open={true} onOpenChange={() => {}} />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Regenerate KHQR/i })).toBeDefined();
    });
  });
});
```

### 4.2 Playwright E2E Test: Full Bakong KHQR Checkout (`e2e/bakong-checkout.spec.ts`)
```ts
import { test, expect } from '@playwright/test';

test.describe('Bakong KHQR Checkout E2E Flow', () => {
  test('Customer creates order, views dynamic KHQR, verifies payment, and sees Paid status', async ({ page }) => {
    let paymentVerified = false;

    await page.route('**/order/42/payment', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'OK',
          data: {
            id: 10,
            order_id: 42,
            amount: '4.50',
            currency: 'USD',
            method: 'khqr',
            status: paymentVerified ? 'paid' : 'pending',
            transaction_ref: paymentVerified ? 'bakong_tx_hash_9001' : 'ORD-42-A1',
            qr_string: '00020101021229190015coffeeshop@aclb6304ABCD',
            qr_md5: 'd60f3db96913029a2af979a1662c1e72',
            expires_at: new Date(Date.now() + 180_000).toISOString(),
            payer_account_masked: paymentVerified ? 'cu***an@aba' : null,
          },
        }),
      });
    });

    await page.route('**/order/42/payment/verify', async (route) => {
      paymentVerified = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'Payment verification completed',
          data: {
            id: 10,
            order_id: 42,
            amount: '4.50',
            currency: 'USD',
            method: 'khqr',
            status: 'paid',
            transaction_ref: 'bakong_tx_hash_9001',
            bakong_transaction_hash: 'bakong_tx_hash_9001',
            payer_account_masked: 'cu***an@aba',
          },
        }),
      });
    });

    await page.goto('/orders/42');
    await page.getByRole('button', { name: /Pay with Bakong KHQR/i }).click();
    await expect(page.getByText('KHQR • BAKONG')).toBeVisible();
    await page.getByRole('button', { name: /I Have Paid — Check Status/i }).click();
    await expect(page.getByText(/Payment Verified!/i)).toBeVisible();
  });
});
```

---

## 5. CI Pipeline Steps (`.github/workflows/ci.yml`) (`[MUST]`)

```yaml
name: Coffee Shop & Bakong KHQR CI
on: [push, pull_request]

jobs:
  backend-ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        working-directory: coffee_shop
        run: pip install -r requirements-dev.txt
      - name: Lint & Mock Pattern Gate
        working-directory: coffee_shop
        run: |
          ruff check .
          python scripts/check_mock_patterns.py
      - name: Run Unit, Bakong KHQR & Integration Tests
        working-directory: coffee_shop
        env:
          PYTHONPATH: ${{ github.workspace }}/coffee_shop/libs/testing
        run: |
          cd user_service && pytest -v
          cd ../operation_service && pytest -v
          cd ../report_service && pytest -v
          cd .. && pytest tests/test_cross_service_integration.py -v

  frontend-ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - name: Install & Type-Check & Lint
        working-directory: coffee_shop_frontend
        run: |
          npm ci
          npm run type-check
          npm run lint
```

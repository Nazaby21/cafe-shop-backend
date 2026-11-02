# Step 4: Unused Code, Features & Dependencies Cleanup Report (`docs/04_CLEANUP_REPORT.md`)

> **Safety Rule Compliance**: Per execution instructions, **no uncertain files or code have been deleted**. Every candidate is categorized below into **"Safe to Delete"** vs **"Needs Confirmation"** with full technical rationale and impact analysis.

---

## 1. Frontend (`coffee_shop_frontend`) Cleanup Inventory

### 1.1 Safe to Delete (Frontend)

| # | Target (File / Symbol / Package) | Category | Evidence / Tool Finding | Reason Safe to Delete |
| :--- | :--- | :--- | :--- | :--- |
| **F-1** | [`src/hooks/useDebounce.ts`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/hooks/useDebounce.ts) | Dead Stub File | Contains only `export {};` (1 line); 0 imports across `src/`. | Empty placeholder file with no implementation or consumers. |
| **F-2** | [`src/hooks/useMediaQuery.ts`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/hooks/useMediaQuery.ts) | Dead Stub File | Contains only `export {};` (1 line); 0 imports across `src/`. | Empty placeholder file with no implementation or consumers. |
| **F-3** | [`src/hooks/usePagination.ts`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/hooks/usePagination.ts) | Dead Stub File | Contains only `export {};` (1 line); 0 imports across `src/`. | Empty placeholder file with no implementation or consumers. |
| **F-4** | [`src/features/dashboard/validation.ts`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/features/dashboard/validation.ts) | Dead Stub File | Contains only comments + `export {};`; 0 imports across `src/`. | Empty placeholder module never imported by `dashboard/page.tsx` or `dashboard/hooks.ts`. |
| **F-5** | `Input` import in [`src/app/(dashboard)/products/page.tsx:13`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/app/(dashboard)/products/page.tsx#L13) | Unused Import | ESLint `@typescript-eslint/no-unused-vars` | Search input was moved to `Navbar`; `Input` is no longer rendered inside `products/page.tsx`. |
| **F-6** | `BarChart3` import & `ROUTES.REPORTS` in [`src/constants/routes.ts:2,27`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/constants/routes.ts#L2) | Unused Import & Dead Route Constant | ESLint `@typescript-eslint/no-unused-vars`; `/reports` page was merged into `/dashboard`. | No `/reports` page exists in `src/app/(dashboard)/`; analytics live on `/dashboard`. |
| **F-7** | Unused `data` callback parameters in [`src/features/category/hooks.ts:23,40,56`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/features/category/hooks.ts#L23) | Unused Variable | ESLint `@typescript-eslint/no-unused-vars` (3 warnings) | `onSuccess: (data) =>` does not use `data`; replacing with `onSuccess: () =>` eliminates 3 lint warnings. |
| **F-8** | Legacy Payment Methods `'card'` and `'e_wallet'` in [`src/types/enums.ts`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/types/enums.ts), [`cart-dialog.tsx`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/features/cart/components/cart-dialog.tsx#L27-L31), and [`pay-dialog.tsx`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/features/payment/components/pay-dialog.tsx#L27-L31) | Non-Bakong Payment Methods | Requirement: *"Integrate ONLY Bakong KHQR, no ABA PayWay or other gateways"* | Replace generic simulated `'card'` / `'e_wallet'` options with `'khqr'` (Bakong KHQR) and `'cash'` (POS staff offline cash). |

### 1.2 Needs Confirmation Before Deleting (Frontend)

| # | Target | Category | Observation | Why Confirmation Is Needed |
| :--- | :--- | :--- | :--- | :--- |
| **FC-1** | `tailwindcss-animate` (`^1.0.7`) in [`package.json`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/package.json#L41) | npm devDependency | Project uses Tailwind CSS v4 (`@tailwindcss/postcss` + `src/styles/globals.css`), and `tailwindcss-animate` is not imported in `globals.css`. | Confirm whether future Radix Dialog/Toast keyframe animations intend to load `tailwindcss-animate` or native CSS `@keyframes`. |
| **FC-2** | `deleteCategory` hook in [`src/app/(dashboard)/categories/page.tsx:44`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/app/(dashboard)/categories/page.tsx#L44) | Unused Hook Call vs Missing UI Button | `const deleteCategory = useDeleteCategory()` is declared in `CategoriesPage` and `DELETE /category/{id}` exists in `operation_service`, but no Delete button is rendered. | Rather than deleting `useDeleteCategory()`, we recommend wiring up the Delete button + `ConfirmDialog` in `CategoriesPage`. |

---

## 2. Backend (`coffee_shop`) & Workspace Cleanup Inventory

### 2.1 Safe to Delete (Backend & Workspace)

| # | Target (File / Directory / Symbol) | Category | Evidence / Tool Finding | Reason Safe to Delete |
| :--- | :--- | :--- | :--- | :--- |
| **B-1** | [`coffee_shop/user_service/app/exceptions/__init__.py`](file:///D:/Study/Year-4/Python/coffee_shop/user_service/app/exceptions/__init__.py) | Empty Dead Package | 0 bytes; all exceptions in `user_service` live in `app/core/exception.py`. | Leftover empty directory from initial scaffolding; 0 references anywhere. |
| **B-2** | `coffee_shop/user_service.db`, `coffee_shop/operation_service.db`, `coffee_shop/report_service.db` | Tracked/Untracked Local SQLite Artifacts | Local SQLite database binary files sitting in `coffee_shop/` root alongside `.gitignore` (`*.db`). | Project constraint is **PostgreSQL ONLY** (with in-memory SQLite or PostgreSQL test DB in pytest fixtures). Binary `.db` files in repo root are stale local artifacts. |
| **B-3** | Duplicate `pydantic-settings==2.16.1` line in [`coffee_shop/requirements-dev.txt:2`](file:///D:/Study/Year-4/Python/coffee_shop/requirements-dev.txt#L2) | Duplicate Dependency | `requirements-dev.txt` includes `-r requirements.txt` on line 1, and `requirements.txt` already pins `pydantic-settings==2.16.1` on line 23. | Redundant duplicate pin in `requirements-dev.txt`. |
| **B-4** | [`test_dashboard.py`](file:///D:/Study/Year-4/Python/test_dashboard.py) (Workspace Root) | Ad-hoc Scratch Script | Hardcodes `"dev-only-shared-secret-change-me"` and `print()` statements calling `localhost:8003`. | Superseded by `coffee_shop/report_service/tests/test_report_api.py` and `coffee_shop/scripts/run_integration_check.py`. |

### 2.2 Needs Confirmation Before Deleting (Backend & Workspace)

| # | Target | Category | Observation | Why Confirmation Is Needed |
| :--- | :--- | :--- | :--- | :--- |
| **BC-1** | `D:\Study\Year-4\Python\venv\` (Root Virtualenv) vs `D:\Study\Year-4\Python\coffee_shop\.venv\` | Duplicate Python Virtual Environments | Two virtual environments exist: `venv/` at workspace root and `.venv/` inside `coffee_shop/`. | Confirm which virtual environment your IDE (PyCharm `.idea/pySourceRootDetection.xml`) is configured to use before removing `venv/`. |
| **BC-2** | `APIM-setup/python-lap.pem` & Root Markdown Reports (`PLAN.md`, `PROJECT_ANALYSIS.md`, `IMPLEMENTATION_REPORT.md`) | Coursework / Infrastructure Artifacts | `APIM-setup/` contains a PEM certificate and the root contains three historical markdown reports. | May be required for university coursework submission or local Gravitee APIM lab setup. Kept untouched. |
| **BC-3** | `PaymentMethod.CARD` and `PaymentMethod.E_WALLET` in [`operation_service/app/models/payment.py`](file:///D:/Study/Year-4/Python/coffee_shop/operation_service/app/models/payment.py#L17-L23) | Legacy Enum Values | Existing historical rows or tests (`test_operation_api.py`) pass `method="card"` when testing the `503` unconfigured gateway path. | When migrating to Bakong KHQR (`method="khqr"` + `method="cash"`), confirm whether historical DB rows in your local PostgreSQL still contain `'card'` or `'e_wallet'` before dropping them from `CHECK` constraints. |
| **BC-4** | `categoryKeys` in [`src/features/category/hooks.ts:6`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/features/category/hooks.ts#L6) vs [`src/constants/queryKeys.ts`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/constants/queryKeys.ts) | Duplicated Query Key Pattern | All other features (`auth`, `products`, `orders`, `users`, `reports`) register their TanStack Query keys in `src/constants/queryKeys.ts`, whereas `category/hooks.ts` defines a local `categoryKeys` object. | Consolidating `categoryKeys` into `queryKeys.categories` is a clean refactor (`[SHOULD]`). |

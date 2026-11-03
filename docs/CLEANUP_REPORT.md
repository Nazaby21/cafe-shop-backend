# Cleanup Report (`docs/CLEANUP_REPORT.md`)

## Executive Summary
This report documents unused code, duplicate dependencies, dead files, and cache artifacts identified across the project. In strict compliance with safety rules, all items are classified as **"Safe to Delete"** or **"Needs Confirmation"**.

---

## 1. Safe to Delete (Confirmed & Actioned)

| Target | Category | Rationale | Action Taken |
|---|---|---|---|
| `coffee_shop/requirements-dev.txt:2` (`pydantic-settings==2.16.1`) | Redundant Dependency | Line 1 includes `-r requirements.txt`, which already specifies `pydantic-settings==2.16.1`. | Removed duplicate dependency pin. |
| `coffee_shop/{clear, dir, docker, where.exe}` | Accidental Empty Files | 0-byte files created by accidental command redirection in terminal. | Deleted files. |
| `.venv/Lib/site-packages/app` (`MyApplication 0.1.0`) | Rogue Virtualenv Package | Stale legacy Flask package shadowing local `app` packages and breaking `pytest` collection. | Uninstalled from `.venv`. |
| `coffee_shop_frontend/node_modules/` in build context | Build Context Bloat | Host Windows binaries transferred across WSL2 9P filesystem. | Blocked via `coffee_shop_frontend/.dockerignore`. |
| `coffee_shop/.venv/`, `coffee_shop/docs/` in build context | Build Context Bloat | Virtualenv and docs copied into image layers. | Blocked via `coffee_shop/.dockerignore`. |

---

## 2. Safe to Delete (Pending User Execution / Confirmation)

| # | Target | Category | Rationale | Safe to Delete? |
|---|---|---|---|---|
| **S-1** | [`coffee_shop_frontend/src/hooks/useDebounce.ts`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/hooks/useDebounce.ts) | Dead Stub File | Contains only `export {};` (1 line); zero imports across `src/`. | **Safe to delete** |
| **S-2** | [`coffee_shop_frontend/src/hooks/useMediaQuery.ts`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/hooks/useMediaQuery.ts) | Dead Stub File | Contains only `export {};` (1 line); zero imports across `src/`. | **Safe to delete** |
| **S-3** | [`coffee_shop_frontend/src/hooks/usePagination.ts`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/hooks/usePagination.ts) | Dead Stub File | Contains only `export {};` (1 line); zero imports across `src/`. | **Safe to delete** |
| **S-4** | [`coffee_shop_frontend/src/features/dashboard/validation.ts`](file:///D:/Study/Year-4/Python/coffee_shop_frontend/src/features/dashboard/validation.ts) | Dead Stub File | Contains only comments + `export {};`; zero imports. | **Safe to delete** |
| **S-5** | `D:\Study\Year-4\Python\test_dashboard.py` | Ad-hoc Scratch Script | Outdated scratch test; superseded by `coffee_shop/report_service/tests/test_report_api.py`. | **Safe to delete** |

---

## 3. Needs Confirmation (Do NOT Delete Automatically)

| # | Target | Category | Observation & Risk | Recommendation |
|---|---|---|---|---|
| **NC-1** | `D:\Study\Year-4\Python\venv\` (Root Virtualenv) | Python Virtual Environment | 2 virtualenvs exist: `D:\Study\Year-4\Python\venv` (root) and `coffee_shop\.venv` (repo). | **MUST KEEP**: Confirm which virtual environment the user's IDE or editor is configured to use before removing either. |
| **NC-2** | `D:\Study\Year-4\Python\APIM-setup\` | External APIM Project | Contains certificates and configurations for an alternate Gravitee APIM setup. | **MUST KEEP**: External coursework project; out of scope. |
| **NC-3** | `PaymentMethod.CARD` and `PaymentMethod.E_WALLET` in `operation_service/app/models/payment.py` | Legacy Enum Values | Retained for backward compatibility with 503 unconfigured gateway test cases. | **SHOULD KEEP**: Do not remove until historical rows in local DB are purged. |
| **NC-4** | `tailwindcss-animate` in `coffee_shop_frontend/package.json` | Dev Dependency | Not directly referenced in CSS imports, but may be used for future Radix UI dialog animations. | **NICE-TO-HAVE**: Keep until Tailwind UI polish is finalized. |

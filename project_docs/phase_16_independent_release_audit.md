# Phase 16 Independent Product Release Audit
**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (2009–2011)  
**Lead Auditor / Combined Team:** Principal ML Engineer, Senior Forecasting Researcher, Applied Statistician, Backend Architect, Security Engineer, Frontend Architect, QA Automation Lead, MLOps Engineer, Independent Academic Auditor  
**Audit Date:** 2026-10-21  
**Project Root:** `c:\Users\thain\Downloads\ML Đồ Án`  
**Governing Standard:** Evidence-First · Zero Fabricated Results · Model Freeze Preserved · No Holdout Rescoring · Reproducible Release  

---

## 1. Physical Workspace & Artifact Forensics

An independent physical scan of the workspace was conducted to establish ground truth regarding all claimed assets, source code, data pipelines, model artifacts, and test suites.

### 1.1 Physical Inventory Reconciliation
- **Raw Transaction Records:** `data/raw/online_retail_II.xlsx` physically exists (SHA-256 verified in inventory).
- **Cleaned Dataset:** `data/interim/online_retail_cleaned.parquet` physically exists (reconciled in Phase 1 with zero unvetted row drops).
- **Canonical Panel Data:** `data/gold/sku_panel_weekly.parquet` physically exists (2,785 SKUs $\times$ 104 weeks = 289,640 rows, 48.7 MB).
- **Feature Manifest:** 51 strictly governed predictors documented in `project_docs/feature_contract.md`. Zero future target leakage.
- **Model Weights (87 Total Artifacts):**
  - Historical 5-fold CV models (78 artifacts) physically present in `artifacts/models/cv/`.
  - Refitted production candidates (9 artifacts) physically present in `artifacts/models/production/`:
    - `catboost_mae_full.cbm` (1.3 MB)
    - `catboost_tweedie_p15_full.cbm` (1.3 MB)
    - `tide_sequence_v1_full.pt` (6.2 MB)
    - 4 cohort-specific models (`CatBoost__MAE_CAUSAL_MATURE`, `CatBoost__MAE_LATE_MATURING`, `TiDE_Sequence_v1_CAUSAL_MATURE`, `TiDE_Sequence_v1_LATE_MATURING`)
    - 2 naive benchmark models (`naive_1.json`, `naive_seasonal_52.json`)
- **Holdout Scoring:** Evaluated once in Phase 8 (`artifacts/evaluation/phase_08_final_holdout_predictions.parquet`, 111,400 rows). Holdout targets remained completely locked; zero holdout rescoring or hyperparameter tuning occurred in Phase 16.

### 1.2 Automated Test Suite Reconciliation
- **Reported Baseline (Phase 15):** 188 automated tests passing.
- **Phase 16 Executable Test Suite:**
  - 188 pre-existing tests.
  - 6 new Calendar Boundary and Temporal Tests (`tests/test_phase16_calendar_and_boundary.py`).
  - 9 new Security Hardening, PBKDF2 600k, RFC 8725 JWT, Injection, and Horizon Guard Tests (`tests/api/test_phase16_security_and_hardening.py`).
  - **Total Executed Tests:** **203 tests**.
  - **Test Outcome:** **203 PASSED, 0 FAILED, 0 SKIPPED, 10 DEPRECATION WARNINGS**.
  - **Execution Time:** 79.50 seconds on Python 3.12.7 (`pytest-8.4.2`).

### 1.3 Frontend Production Build Verification
- **Framework:** React 18.3.1 + TypeScript + Vite 5.4.2 + Tailwind CSS + Lucide Icons + Recharts.
- **Build Execution:** `npm run build` executed in `frontend/`.
- **Output:** Built production bundle located at `frontend/dist/` (HTML, JS bundle 498.42 kB gzip: 147.28 kB, CSS 37.19 kB gzip: 7.02 kB).
- **Compilation Time:** 3.09 seconds with 0 errors and 0 lint warnings.

---

## 2. Forensic Resolutions of Critical Defects

### 2.1 DEF-16-01: Horizon Discrepancy Remediated (P0)
- **Defect:** Model Registry advertised `supported_horizons=[1..8]`, the Forecast API accepted $H \le 8$, and the frontend dropdown offered $H=8$, even though CatBoost MAE was officially authorized for $H=1..4$.
- **Remediation:**
  1. Constrained `supported_horizons` in `src/services/model_registry.py` strictly to `[1, 2, 3, 4]`.
  2. Updated `src/api/schemas/forecast.py` with `horizon_weeks: conint(ge=1, le=4)`.
  3. Added runtime check in `src/services/forecasting_service.py` raising `UnsupportedHorizonException` (HTTP 422, code `UNSUPPORTED_HORIZON`).
  4. Updated `frontend/src/pages/ForecastPage.tsx` select dropdown to strictly provide horizons 1, 2, 3, and 4.
  5. Recompiled frontend production bundle and regenerated `project_docs/openapi.json`.
  6. Added automated validation tests verifying rejection of $H \in \{0, 5, 8\}$.

### 2.2 DEF-16-02: Replenishment Horizon Extrapolation Blocked (P1)
- **Defect:** If protection period $L+R$ exceeded available forecast steps, `planning_service.py` silently summed available steps, causing under-procurement without alerting the user.
- **Remediation:** Enforced strict guard: `if (lead_time + review_period) > max_available_horizon`, raises `AppException(status_code=422, error_code=VALIDATION_ERROR)` explicitly notifying the user that the requested protection interval exceeds the model's valid forecast horizon.

### 2.3 DEF-16-03: PBKDF2 Password Hashing Upgraded to 600,000 Iterations (P1)
- **Defect:** Legacy 100,000 iterations fell below current OWASP Password Storage recommendations.
- **Remediation:**
  1. Default iterations upgraded to 600,000.
  2. Transparent auto-rehash implemented on successful login for legacy user hashes.
  3. Added administrative bootstrap endpoint `POST /api/v1/auth/bootstrap` for secure credential rotation.

### 2.4 DEF-16-04: JWT RFC 8725 Conformance Hardened (P2)
- **Defect:** Decoding lacked explicit algorithm allowlisting, and token lifetime was 480 minutes (8 hours).
- **Remediation:** Enforced `algorithms=["HS256"]` in `decode_access_token`, mandatory `exp`, `nbf`, `iat` validation with 5s clock skew, and reduced default access token lifetime to 120 minutes (2 hours).

### 2.5 DEF-16-05 & DEF-16-06: Export Injection & Path Traversal Neutralized (P2)
- **Defect:** Unsanitized CSV cells could permit formula/DDE execution, and unvalidated paths could permit traversal.
- **Remediation:** Implemented `sanitize_csv_cell` prefixing `=, +, -, @, \t, \r` with `'`. Path traversal sequences (`..`, `/`, `\`) rejected with HTTP 400/404.

---

## 3. Data Contract & Population Semantics

### 3.1 Canonical Weekly Boundary Contract
The temporal pipeline was audited to ensure mathematical consistency:
- **Canonical Definition:** W-MON ISO Monday 00:00:00 floor interval $[t_{\text{start}}, t_{\text{end}})$.
- **Half-Open Interval:** A transaction timestamp $t$ belongs to week $W$ starting at Monday 00:00:00 if and only if $W \le t < W + 7 \text{ days}$.
- **Boundary Test Evidence (`tests/test_phase16_calendar_and_boundary.py`):**
  - Sunday 23:59:59 correctly maps to the preceding Monday.
  - Monday 00:00:00 marks the exact week start.
  - Monday 23:59:59 remains within the same Monday week.
  - First raw invoice (`2009-12-01 07:45:00`, Tuesday) correctly maps to week `2009-11-30`.
  - Last raw invoice (`2011-12-09 12:50:00`, Friday) correctly maps to week `2011-12-05`.
  - Timezone-aware conversions preserve identical Monday calendar boundaries.

### 3.2 Panel Completeness & Lifecycle Semantics
- **Panel Population:** 2,785 active SKUs across 104 contiguous weeks (289,640 records).
- **Observed Zeros vs Pre-Launch Periods:**
  - True observed zero-demand weeks occurring after an SKU's first commercial transaction are encoded as zero demand with observed activity flags.
  - Pre-launch unobserved intervals are distinguished in the metadata and feature pipeline to prevent artificial zero-demand bias.

### 3.3 Product Categorization Governance
- **Volume ABC:** Cumulative Pareto classification based on unit sales quantity (A: top 80%, B: next 15%, C: bottom 5%).
- **Value ABC:** Cumulative Pareto classification based on gross revenue proxy (`quantity * unit_price`).
- **XYZ Volatility:** Coefficient of variation ($CV = \sigma / \mu$): X ($CV \le 0.5$), Y ($0.5 < CV \le 1.0$), Z ($CV > 1.0$).
- **SBC Classification:** Syntetos-Boylan-Croston demand regime matrix partitioning SKUs by Average Demand Interval ($ADI$) and squared coefficient of variation ($CV^2$): Smooth, Intermittent, Erratic, and Lumpy.

---

## 4. Browser-Level Frontend Acceptance Verification

A real, headless browser subagent session was executed against the live application mounted on `http://127.0.0.1:8000`:

| Screen / Feature | Verified Behavior | Verdict |
|---|---|---|
| **1. Authentication Portal** | Renders login dialog, cryptographic security indicators (`PBKDF2-HMAC-SHA256 • JWT HS256`), and role quick-switch buttons. | **PASS** |
| **2. Executive Dashboard** | Displays 2,785 Qualified Panel SKUs, 104-week span (96 development + 8 holdout), ABC breakdown, and dataset lineage. | **PASS** |
| **3. Demand Forecasting** | Horizon dropdown strictly constrained to $H \in \{1, 2, 3, 4\}$. Executed SKU 10002 forecast with CatBoost MAE; returned 4 weekly predictions. | **PASS** |
| **4. SKU Explorer** | Searched SKU 10002, inspected weekly demand time series chart, classification badges (Causal Mature, ABC category). | **PASS** |
| **5. Replenishment Planning** | Simulated $(R, S)$ policy for SKU 10002 ($L=2, R=1, SS=15$). Displayed gross/net requirements and disclaimer `SIMULATION_BASED_ON_USER_ASSUMPTIONS`. | **PASS** |
| **6. Model Leaderboard** | Verified CV vs final holdout metrics (WAPE, MAE, RMSE, signed bias). Confirmed CatBoost MAE champion status. | **PASS** |
| **7. Model Registry** | Verified model artifacts, `SERVING_READY` status, supported horizons $H=1..4$, and SHA-256 integrity digests. | **PASS** |
| **8. Run History & Exports** | Verified forecast run audit trail with user attribution. Generated and validated CSV export artifact. | **PASS** |
| **9. Admin Role & User Management** | Logged in as `admin`. Verified access to `/admin/users` displaying the 4 active seed accounts (`admin`, `analyst`, `planner`, `viewer`). | **PASS** |
| **10. Viewer Role Restrictions** | Logged in as `viewer`. Verified read-only access where forecast triggering is disabled with explicit governance messaging. | **PASS** |
| **11. Session Expiration & Logout** | Verified logout invalidates the JWT session and safely returns the client to the login screen. | **PASS** |

---

## 5. Model Freeze & Holdout Governance

### 5.1 Single Holdout Evaluation Policy Preserved
- The holdout window (`2011-10-10` to `2011-11-28`, 8 weeks) was evaluated exactly once in Phase 8.
- **Zero Holdout Rescoring:** The holdout targets were neither opened, recalculated, nor used for hyperparameter tuning in Phase 16.
- **Zero Retraining:** No models were retrained. All serving artifacts maintain their exact frozen states and cryptographic hashes.

### 5.2 Mandatory Historical Applicability Disclaimer
- The application and documentation strictly preserve:
  ```
  current_market_applicability_assessed = FALSE
  ```
- **Operational Reality:** The underlying transaction dataset spans December 2009 to December 2011. While the system demonstrates state-of-the-art causal forecasting, feature engineering, and software engineering rigor, **it is not calibrated for immediate commercial use in today's retail market without contemporary data collection and a newly justified training cycle.**

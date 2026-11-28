# Smart Inventory Intelligence & Demand Forecasting System

A retail inventory intelligence and weekly demand forecasting system designed to help small retailers understand product demand, anticipate stockout risks, and compute indicative reorder quantities using clear, plain-language outputs.

> **Dataset Note**: `sales_data.csv` is a synthetic daily retail dataset (76,000 rows across 5 stores, 20 products, and 760 dates from `2022-01-01` to `2024-01-30`). All results demonstrate prototype behavior and do **not** claim real-world kirana-shop validation.

---

## Project Architecture & Directory Structure

```text
INVENTORY INTELLIGENCE AND STOCK PREDICTION/
│
├── NoteBook_01.ipynb                            # End-to-end prototype (18 sections, calls backend modules)
├── sales_data.csv                               # Source daily retail dataset (76,000 rows, unmodified)
├── weekly_product_demand.csv                    # Weekly W-SUN aggregated dataset (2,200 product-weeks)
│
├── frontend/                                    # Part 3 React + Vite web application
│   ├── package.json
│   ├── vite.config.js                           # Proxies /api/* to Flask (port 5000)
│   └── src/
│       ├── components/                          # Layout, upload dropzone, badges, charts
│       ├── pages/                               # Home, FutureSales, MyStock, WhatToOrder, Settings
│       ├── services/api.js                      # Centralised Flask API client
│       ├── styles/                              # Unslop design tokens & component styles
│       └── utils/format.js                      # Locale formatting & backend state mapping
│
├── backend/
│   ├── app.py                                   # Flask application factory and server entry point
│   ├── config.py                                # Central configuration (upload limits, schema, W-SUN)
│   ├── requirements.txt                         # Python dependencies
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── demand_forecaster.py                 # Moving-average baseline & RandomForestRegressor wrappers
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── upload_routes.py                     # POST /api/upload & GET /api/health (Part 1 API)
│   │   └── analysis_routes.py                   # GET /, POST /api/analyze, /api/forecast, /api/recommendations
│   │
│   ├── static/
│   │   └── index.html                           # Integrated web dashboard served by Flask
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── csv_loader.py                        # Stream-safe CSV reading into DataFrame
│   │   ├── csv_validator.py                     # Schema and data-quality validation rules
│   │   ├── data_preprocessor.py                 # Datetime conversion, trimming, chronological sorting
│   │   ├── weekly_aggregator.py                 # Sunday-ending (W-SUN) weekly demand aggregation
│   │   ├── feature_engineering.py               # Leakage-safe lag, rolling, and calendar features
│   │   ├── model_evaluation.py                  # MAE, RMSE, WAPE, R², per-product metrics & conformal calibration
│   │   ├── forecasting_service.py               # Validated 1..12 week recursive forecasting & multi-step eval
│   │   ├── inventory_analysis.py                # Verified opening/closing stock & movement tier analysis
│   │   ├── replenishment_service.py             # Indicative order recommendations & plain-language messages
│   │   └── pipeline_service.py                  # Stateful Part 3 orchestration & session cache
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   └── error_handlers.py                    # Standardized JSON error responses
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_validation.py                   # Schema & data quality checks
│       ├── test_preprocessing.py                # Preprocessing & non-mutation checks
│       ├── test_weekly_aggregation.py           # W-SUN, cross-store sum, no zero-filling checks
│       ├── test_feature_engineering.py          # Lag/rolling leakage & chronological split checks
│       ├── test_model_evaluation.py             # WAPE zero-denom, model parity, conformal coverage checks
│       ├── test_forecasting.py                  # Horizon bounds & recursive forecasting checks
│       ├── test_inventory_and_replenishment.py  # Stock semantics, zero floor, & assumption checks
│       ├── test_upload.py                       # Part 1 Flask upload API endpoint tests
│       ├── test_analysis_api.py                 # Part 3 integrated analyze, forecast & UI route tests
│       └── test_notebook_parity.py              # Notebook 01 & Part 2 end-to-end parity tests
│
├── README.md
└── .gitignore
```

---

## Environment Setup & Execution

### Prerequisites
- Python 3.10+ (verified on Python 3.14.0)

### 1. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 2. Run the Automated Test Suite (42 Tests)
```bash
python -m pytest backend/tests -v
```

### 3. Execute `NoteBook_01.ipynb` in a Clean Environment
Open `NoteBook_01.ipynb` in Jupyter / VS Code and run all cells top-to-bottom from the repository root, or execute headlessly with `nbclient` / `jupyter nbconvert --execute NoteBook_01.ipynb`.

### 4. Start the Smartventory Web App & Flask API
```bash
# Terminal 1: Start the Flask backend API (also serves standalone HTML at /)
python backend/app.py
```

```bash
# Terminal 2: Start the React + Vite frontend (recommended Part 3 UI)
cd frontend
npm install
npm run dev
```
Then open **`http://localhost:3000`** for the React + Vite dashboard (proxies `/api/*` to `http://127.0.0.1:5000`), or open **`http://127.0.0.1:5000/`** for the Flask-served standalone HTML view. See [`frontend/README.md`](frontend/README.md) for production build and environment configuration details.

Available backend endpoints:
- `GET /` — Serves the standalone Flask HTML dashboard
- `GET /api/health` — Health check
- `POST /api/upload` — Part 1 CSV summary endpoint
- `POST /api/analyze` — Runs full Part 2 validation, Random Forest training, conformal calibration, inventory analysis, and recommendations (`file` upload or `{"use_demo": true}`)
- `POST /api/forecast` — Generates 1–12 week recursive forecast with 80% bounds (`{"dataset_id", "product_id", "horizon_weeks"}`)
- `POST /api/recommendations` — Recalculates reorder suggestions with custom `lead_time_weeks` and `safety_stock_weeks`

Example (`POST /api/analyze`):
```bash
curl -X POST http://127.0.0.1:5000/api/analyze -F "file=@sales_data.csv"
```

---

## Part 2 Summary: Forecasting, Uncertainty & Inventory Intelligence

### Leakage-Safe Features & Training Protocol
- **Aggregation**: Daily `Demand` summed across all 5 stores per `Product ID` into Sunday-ending calendar weeks (`W-SUN`), producing **2,200 product-week rows** (20 products × 110 weeks, `2022-01-02` to `2024-02-04`). First and last calendar weeks contain 2 active operating days each and are retained transparently.
- **Chronological Split**: Earliest 80% of unique weeks (88 weeks, `2022-01-02` to `2023-09-03`) for training (`1,680` lag-complete rows); latest 20% (22 weeks, `2023-09-10` to `2024-02-04`) for rolling one-week-ahead evaluation (`440` identical eligible test rows).
- **Features**: `product_code` (fitted on training products only), `lag_1`..`lag_4`, `roll_mean_4`, `roll_std_4`, `roll_mean_8` (computed strictly on `shift(1)`), `week_of_year`, `month`. Future `Units Sold`, `Inventory Level`, and unguaranteed future external columns are excluded.
- **Model**: `RandomForestRegressor(n_estimators=200, max_depth=10, min_samples_leaf=3, random_state=42, n_jobs=-1)`.

### Baseline vs. Random Forest (440 Eligible Test Rows)
- **4-Week Moving Average**: MAE = **663.63**, RMSE = **880.25**, WAPE = **19.57%**, R² = **-0.1101**
- **Random Forest Regressor**: MAE = **569.37**, RMSE = **870.01**, WAPE = **16.79%**, R² = **-0.0844**
- **Full 7-Day Weeks Sensitivity (420 rows, excluding 2-day final week `2024-02-04`)**:
  - Moving Average: MAE = **579.44**, RMSE = **724.63**, WAPE = **16.53%**, R² = **-0.1810**
  - Random Forest: MAE = **456.57**, RMSE = **615.91**, WAPE = **13.02%**, R² = **+0.1468**

### Multi-Horizon Recursive Evaluation & Split-Conformal Intervals
- Supports preset horizons **1, 2, 4, 8 weeks** and custom horizons **1–12 weeks** (`validate_horizon`).
- Multi-step predictions feed prior predicted values back as lags (never future actuals) and calibrate 80% split-conformal intervals separately per step on a 22-week out-of-sample validation slice without touching final test rows.

### Inventory Semantics, Stockout & Replenishment Assumptions
- **Verified Stock Meaning**: `Inventory Level` is start-of-day opening inventory (`Units Sold <= Inventory Level` on all 76,000 rows, zero negative stock deltas). Closing stock at the end of the latest observed date (`2024-01-30`) is `sum(Inventory Level - Units Sold)` across stores per product.
- **Snapshot Disclosure**: All stock analysis reflects the uploaded historical dataset (`2024-01-30`), not real-time live store stock.
- **Replenishment Formula**: `Suggested order = max(0, round(expected_weekly_demand * (lead_time_weeks + safety_stock_weeks) - available_stock - confirmed_incoming_stock))`.
- **Assumptions**: Supplier lead times in the historical data vary 1–5 days and pack sizes/MOQs are absent; defaults (`1.0`-week lead time, `0.5`-week safety buffer, `0` confirmed incoming stock) are configurable and labeled as indicative decision support only.

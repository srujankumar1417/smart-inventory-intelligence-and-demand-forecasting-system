# Smart Inventory Intelligence & Demand Forecasting System

A retail inventory intelligence and demand forecasting system designed to optimize supply chain replenishment, mitigate stockouts, and minimize holding costs.

---

## Project Architecture & Directory Structure

```text
INVENTORY INTELLIGENCE AND STOCK PREDICTION/
│
├── NoteBook_01.ipynb                            # Milestone 01: Baseline notebook (executed with outputs)
├── Smartventory_01_Understanding_and_Analysis.md# Technical background & mathematical formulations
├── sales_data.csv                               # Source retail dataset (76,000 rows, 2022-01-01 to 2024-01-30)
├── weekly_product_demand.csv                    # Aggregated baseline dataset (2,200 product-weeks)
│
├── backend/                                     # Part 1: Refactored data pipeline & Flask backend
│   ├── app.py                                   # Flask application factory and server entry point
│   ├── config.py                                # Central configuration (upload limits, schema, W-SUN)
│   ├── requirements.txt                         # Backend dependencies
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   └── upload_routes.py                     # POST /api/upload & GET /api/health
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── csv_loader.py                        # Stream-safe CSV reading into DataFrame
│   │   ├── csv_validator.py                     # Schema and data-quality validation rules
│   │   ├── data_preprocessor.py                 # Datetime parsing, sorting, and cleaning
│   │   └── weekly_aggregator.py                 # Sunday-ending weekly product demand aggregation
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   └── error_handlers.py                    # Standardized JSON error response handlers
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                          # Pytest fixtures and mock client
│       ├── test_validation.py                   # Schema and data quality validation unit tests
│       ├── test_preprocessing.py                # Preprocessor transformation unit tests
│       ├── test_weekly_aggregation.py           # Weekly demand aggregation unit tests
│       ├── test_upload.py                       # Flask upload API endpoint tests
│       └── test_notebook_parity.py              # Exact parity test against Notebook 01 output
│
├── README.md
└── .gitignore
```

---

## Milestone 01: Baseline Results Summary

- **Forecasting Unit**: One product-week (`Weekly_Demand` per `Product ID` across all stores).
- **Evaluation Strategy**: Chronological 80/20 train/test split on unique weeks (88 training weeks, 22 test weeks) in a rolling one-week-ahead setup.
- **Baseline Model**: 4-week trailing moving average per product with 1-week shift (`shift(1)`) to strictly prevent target leakage.
- **Evaluated Test Observations**: 440 valid product-weeks (0 exclusions).
- **Primary Metric (MAE)**: **663.63 units**
- **Supporting Metric (RMSE)**: **880.25 units**
- **Supporting Metric ($R^2$)**: **-0.1101**

---

## Part 1: Data Pipeline Refactoring & Flask Backend

Part 1 converts the data ingestion, validation, and aggregation logic from Notebook 01 into modular, reusable Python services exposed via a clean Flask API.

### Key Service Modules
1. **`csv_loader.py`**: Reads `FileStorage`, byte streams, buffers, or file paths with automated encoding detection and empty/corrupted file detection.
2. **`csv_validator.py`**: Validates schema presence, null checks, date validity, non-negative demand, non-blank product IDs, and reports duplicate triplets.
3. **`data_preprocessor.py`**: Safely copies data, casts `Date` to datetime and `Demand` to numeric, strips identifier whitespace, and sorts chronologically.
4. **`weekly_aggregator.py`**: Resamples demand into Sunday-ending calendar weeks (`W-SUN`) per `Product ID` summed across all stores. Retains boundary partial weeks without synthetic zero-filling.

---

## Environment Setup & Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- pip

### Dependency Installation
```bash
pip install -r backend/requirements.txt
```

---

## Running the Automated Test Suite

The test suite validates data ingestion, schema enforcement, preprocessing, weekly aggregation, API error responses, and **exact parity against Notebook 01**:

```bash
python -m pytest backend/tests -v
```

### Verified Test Results
- **Total Tests**: 25 passed in 0.50s (0 failures, 0 skipped).
- **Parity Verification**: Exact match across all 2,200 rows, 20 products, 110 weeks, and total demand of 7,928,104 units between `backend` pipeline and `weekly_product_demand.csv`.

---

## Running the Flask Backend

To start the Flask development server:

```bash
python backend/app.py
```
Or:
```bash
python -m backend.app
```
The server will start on `http://127.0.0.1:5000`.

---

## API Documentation

### 1. Health Check
- **Endpoint**: `GET /api/health`
- **Response**:
```json
{
  "service": "Smartventory Data Pipeline API",
  "status": "healthy",
  "version": "1.0.0"
}
```

### 2. Upload & Process Dataset
- **Endpoint**: `POST /api/upload`
- **Content-Type**: `multipart/form-data`
- **Form Field**: `file` (must be a valid `.csv` file, max size 16MB)

#### Example Request (`curl`)
```bash
curl -X POST http://127.0.0.1:5000/api/upload \
  -F "file=@sales_data.csv"
```

#### Example Successful Response (`200 OK`)
```json
{
  "status": "success",
  "message": "Dataset validated and processed successfully.",
  "data_summary": {
    "total_records": 76000,
    "total_columns": 16,
    "unique_products": 20,
    "unique_stores": 5,
    "weekly_records": 2200,
    "unique_weeks": 110,
    "week_start": "2022-01-02",
    "week_end": "2024-02-04",
    "total_weekly_demand": 7928104,
    "first_week_days": 2,
    "last_week_days": 2,
    "has_partial_weeks": true
  },
  "weekly_schema": [
    "Product ID",
    "Week_Ending",
    "Weekly_Demand"
  ],
  "notes": [
    "Weekly demand is aggregated across all stores.",
    "The first and last calendar weeks may be partial."
  ]
}
```

#### Example Error Response (`400 Bad Request`)
```json
{
  "status": "error",
  "error_code": "MISSING_REQUIRED_COLUMNS",
  "message": "The uploaded CSV is missing required columns: Demand",
  "details": {
    "missing_columns": ["Demand"]
  }
}
```

---

## CSV Schema Specification

### Required Columns (Pipeline Minimum)
- `Date`: Valid calendar date string (`YYYY-MM-DD`).
- `Product ID`: Non-empty product identifier (e.g. `P0001`).
- `Demand`: Non-negative numeric demand value.

### Expected Columns (Full Retail Catalog)
`Date`, `Store ID`, `Product ID`, `Category`, `Region`, `Inventory Level`, `Units Sold`, `Units Ordered`, `Price`, `Discount`, `Weather Condition`, `Promotion`, `Competitor Pricing`, `Seasonality`, `Epidemic`, `Demand`.

---

## Roadmap & Handover to Part 2

- **Part 1 (Completed)**: Reusable data pipeline, schema validation, weekly demand aggregation, Flask backend API, and comprehensive test suite with Notebook 01 parity.
- **Part 2 (Next Phase)**: Random Forest Regressor integration, user-defined forecasting horizons, stockout estimation, and replenishment quantity recommendations.

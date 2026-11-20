# Smartventory: Notebook 01 — Comprehensive Understanding, Methodology & Analysis Guide

This document provides the in-depth conceptual framework, mathematical formulations, operational justifications, and analytical findings for **Notebook 01: Weekly Demand Forecasting Baseline (`Smartventory_01_Weekly_Demand_Baseline.ipynb`)**.

---

## 1. Project Objective & Context

In retail supply chains and warehouse inventory management, accurate demand forecasting is critical for optimizing replenishment cycles, minimizing stockout penalties, and reducing holding costs and perishable waste. 

### Core Forecasting Task
- **Target Variable**: Total aggregate demand for each product during a calendar week (`Weekly_Demand`).
- **Forecasting Unit**: One `Product ID` $\times$ calendar week.
- **Aggregation Scope**: Daily demand is summed across all retail store locations (`Store ID`).
- **Forecast Horizon**: One week ahead ($t+1$).
- **Baseline Model**: 4-week trailing moving average computed per product.
- **Subsequent Stage (Notebook 02)**: Supervised machine learning via Random Forest Regressor, to be evaluated under the identical chronological split and evaluation scheme.

---

## 2. Dataset Architecture & Validation Profile

### Source Data: `sales_data.csv`
The raw dataset contains daily operational retail records.

| Attribute | Verified Value | Analytical Interpretation |
| :--- | :--- | :--- |
| **Total Rows** | 76,000 | 760 dates $\times$ 5 stores $\times$ 20 products |
| **Total Columns** | 16 | Operational, promotional, pricing, and environmental variables |
| **Date Range** | `2022-01-01` to `2024-01-30` | 760 consecutive unique days |
| **Store Locations** | 5 stores (`S001` to `S005`) | Regional distributed retail network |
| **Product SKUs** | 20 products (`P0001` to `P0020`) | Diversified catalog across 5 merchandise categories |
| **Categories** | 5 | Clothing, Electronics, Furniture, Groceries, Toys |
| **Regions** | 4 | North, South, East, West |
| **Data Cleanliness** | 0 nulls, 0 duplicate rows | Clean tabular data; no synthetic imputation required |
| **Target Validity** | Min Demand: 4, Max Demand: 430 | Non-negative integer demand across all records |
| **Key Uniqueness** | 0 duplicate `(Product, Store, Date)` keys | Exactly one record per product per store per day |

---

## 3. Weekly Aggregation Rationale & Mechanics

### Why Aggregate Across All Stores?
1. **Supply Chain Order Alignment**: Warehouse procurement orders and vendor delivery contracts operate at the regional distribution center level rather than individual retail shelf level.
2. **Noise Reduction & Stability**: Store-level daily sales are susceptible to local cashier outages, single-customer bulk purchases, and localized stockouts. Aggregating across stores produces a smooth, continuous demand curve.
3. **Elimination of Zero-Inflation**: Store-day combinations often feature sparse zero-demand days, requiring complex hurdle models. Network-level weekly demand is strictly positive and well-behaved.

### Resampling Strategy: Sunday-Ending Calendar Weeks (`W-SUN`)
- The daily time series is grouped by `Product ID` and resampled using pandas `pd.Grouper(key='Date', freq='W-SUN')`.
- All daily demand values within Monday–Sunday are summed to form `Weekly_Demand`.

### Disclosure of Boundary Partial Weeks
Because the source dataset begins on Saturday `2022-01-01` and ends on Tuesday `2024-01-30`:
- **First Calendar Week (`2022-01-02`)**: Contains only **2 operating days** (Saturday & Sunday).
- **Final Calendar Week (`2024-02-04`)**: Contains only **2 operating days** (Monday & Tuesday).
- **Intermediate Weeks (108 weeks)**: Contain complete **7 operating days**.
- Both partial weeks are intentionally preserved in the dataset to avoid date truncation, but their partial nature is accounted for when evaluating moving averages and subsequent models.

### Sequence Continuity
- Total aggregated rows: **2,200 rows** ($20 \text{ products} \times 110 \text{ weeks}$).
- Every product possesses an uninterrupted sequence of 110 calendar weeks without missing dates or gaps.

---

## 4. Four-Week Trailing Moving Average Formulation

### Mathematical Definition
For product $p$ at week $t$, the forecast $\widehat{Y}_{p, t}$ is the arithmetic mean of the preceding 4 actual observed weekly demand values:

$$\widehat{Y}_{p, t} = \frac{1}{4} \left( Y_{p, t-1} + Y_{p, t-2} + Y_{p, t-3} + Y_{p, t-4} \right) = \frac{1}{4} \sum_{k=1}^{4} Y_{p, t-k}$$

### Strict Leakage Prevention Rules
1. **Product Isolation**: Grouped strictly by `Product ID`. Demand from one product never contaminates another.
2. **Explicit Shift Operator**: The series is shifted by 1 week (`.shift(1)`) prior to rolling computation (`rolling(window=4, min_periods=4).mean()`).
   - Ensures that actual demand at week $t$ ($Y_{p, t}$) is **never** accessible when predicting week $t$.
3. **Warm-up Window**: The first 4 chronological weeks for every product evaluate to `NaN` because 4 prior historical observations are strictly required.

---

## 5. Evaluation Methodology: Rolling One-Week-Ahead

### Chronological 80 / 20 Train-Test Split
Rather than random splitting (which destroys temporal autocorrelation and leaks future trends into past rows), partitioning is conducted chronologically on unique sorted `Week_Ending` dates:
- **Training Period (80%)**: Earliest 88 weeks (`2022-01-02` to `2023-09-03`), 1,760 product-week observations.
- **Testing Period (20%)**: Latest 22 weeks (`2023-09-10` to `2024-02-04`), 440 product-week observations.
- **Partition Synchronization**: All products for a given week reside in the same partition.

### Rolling One-Week-Ahead Mechanics
- In operational retail deployment, forecasts are updated weekly as new actual sales figures close.
- When forecasting week $t$ in the test set, actual demand values from weeks $t-1, t-2, t-3, t-4$ are available (even if those prior weeks fall in the test period).
- **Leakage Safety**: At no point does the model see current week demand $Y_t$ or future demand $Y_{t+k}$.
- **Exclusion Rate**: Because 88 training weeks precede the test split, all 440 test observations have full 4-week lookback histories available. **Zero test rows are excluded.**

---

## 6. Evaluation Metrics & Verified Empirical Findings

### Metric Formulations & Results (Test Horizon: 440 Observations)

| Metric | Formula | Value | Interpretation |
| :--- | :--- | :--- | :--- |
| **MAE (Primary)** | $\frac{1}{N}\sum \|Y_i - \widehat{Y}_i\|$ | **663.6295** | On average, forecast deviates by ~663.6 units (~12.2% of mean demand). |
| **RMSE (Supporting)** | $\sqrt{\frac{1}{N}\sum (Y_i - \widehat{Y}_i)^2}$ | **880.2499** | Higher than MAE; reflects larger squared penalties on sudden demand spikes and boundary drops. |
| **$R^2$ (Supporting)** | $1 - \frac{\sum (Y_i - \widehat{Y}_i)^2}{\sum (Y_i - \bar{Y})^2}$ | **-0.1101** | Negative $R^2$ demonstrates that trailing unweighted lag performs worse than predicting the horizontal test mean. |

### Why is $R^2$ Negative for the Baseline?
In time-series forecasting, an unweighted trailing moving average has an inherent phase lag:
1. **Lag During Surges**: When promotional campaigns or seasonal spikes occur, the moving average takes 4 weeks to adjust upward.
2. **Lag During Dips**: When demand drops (particularly during the 2-day partial week ending `2024-02-04` where actual demand dropped to ~1,500 units), the baseline still predicts ~5,600 units based on preceding 7-day weeks.
3. **Benchmark Role**: A negative $R^2$ for a trailing simple moving average is normal and establishes a baseline benchmark for machine learning models.

---

## 7. Strategic Decisions for Notebook 02 (Random Forest)

To ensure a rigorous, scientifically valid comparison against this baseline in Notebook 02:
1. **Target and Unit Parity**: Use the exact same target (`Weekly_Demand` per product) and identical chronological test window (latest 22 weeks).
2. **Feature Engineering**:
   - **Autoregressive Lags**: Lags at $t-1, t-2, t-3, t-4$ matching the baseline's information boundary.
   - **Rolling Statistics**: Rolling mean, standard deviation, and min/max over 4 and 8-week windows.
   - **Exogenous Retail Features**: Average price, average discount percentage, network promotion intensity (`mean(Promotion)`), and competitor price differentials.
   - **Calendar & Operational Flags**: Month of year, week of year, and an explicit `Operating_Days` feature (e.g. 2 for boundary weeks, 7 for full weeks) to naturally resolve partial week demand shifts.
3. **Benchmark Success Criterion**: The Random Forest model must achieve an MAE substantially lower than **663.63** and a positive $R^2$ score.


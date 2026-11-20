# Smart Inventory Intelligence & Demand Forecasting System

A retail inventory intelligence and demand forecasting system designed to optimize supply chain replenishment, mitigate stockouts, and minimize holding costs.

---

## Repository Structure

- **[NoteBook_01.ipynb](NoteBook_01.ipynb)**: Executable Jupyter Notebook implementing Milestone 01 — Weekly demand aggregation per product across stores and evaluation of a 4-week trailing moving average baseline.
- **[Smartventory_01_Understanding_and_Analysis.md](Smartventory_01_Understanding_and_Analysis.md)**: In-depth technical documentation covering problem formulation, retail supply chain context, data validation profiles, chronological split methodology, and empirical baseline findings.
- **[sales_data.csv](sales_data.csv)**: Daily retail operations dataset across 5 stores and 20 products (76,000 rows, 2022-01-01 to 2024-01-30).
- **[weekly_product_demand.csv](weekly_product_demand.csv)**: Aggregated weekly dataset (2,200 product-weeks) resampled to Sunday-ending calendar weeks (`W-SUN`).

---

## Milestone 01: Baseline Results Summary

- **Forecasting Unit**: Product-week (`Weekly_Demand` per `Product ID` across all stores).
- **Evaluation Strategy**: Chronological 80/20 train/test split on unique weeks (88 training weeks, 22 test weeks) in a rolling one-week-ahead setup.
- **Baseline Model**: 4-week trailing moving average per product with 1-week shift (`shift(1)`) to strictly prevent target leakage.
- **Evaluated Test Observations**: 440 valid product-weeks (0 exclusions).
- **Primary Metric (MAE)**: **663.63 units**
- **Supporting Metric (RMSE)**: **880.25 units**
- **Supporting Metric ($R^2$)**: **-0.1101**

---

## Roadmap

- **Notebook 01**: Weekly Demand Moving Average Baseline (Completed).
- **Notebook 02**: Random Forest Regressor incorporating autoregressive lags, rolling statistics, promotional intensity, pricing differentials, and operational calendar features.

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


FEATURE_COLUMNS: List[str] = [
    "product_code",
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_4",
    "roll_mean_4",
    "roll_std_4",
    "roll_mean_8",
    "week_of_year",
    "month",
]


def build_product_mapping(product_ids: pd.Series) -> Dict[str, int]:
    """
    Create a deterministic Product ID -> integer code mapping.
    Should be fitted on training product IDs only to avoid encoding leakage.
    """
    unique_sorted = sorted(str(p) for p in product_ids.unique())
    return {pid: idx for idx, pid in enumerate(unique_sorted)}


def build_lag_and_calendar_features(
    weekly_df: pd.DataFrame,
    product_mapping: Optional[Dict[str, int]] = None,
    drop_na: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Engineer leakage-safe lag, trailing rolling, and calendar features per Product ID.

    Leakage prevention guarantees:
    - All lag and rolling features are grouped strictly by Product ID and sorted by Week_Ending.
    - Rolling statistics operate on shift(1) so week t's target never enters its own features.
    - Calendar features (week_of_year, month) are deterministically known from Week_Ending.
    - External variables not guaranteed to be known in future weeks (e.g., future Units Sold,
      future Inventory Level, future Weather) are intentionally excluded.

    Returns:
        Tuple of (featured_df, product_mapping).
    """
    if weekly_df is None or weekly_df.empty:
        raise ValueError("Cannot engineer features from an empty DataFrame.")

    df = weekly_df.copy()
    df["Week_Ending"] = pd.to_datetime(df["Week_Ending"])
    df = df.sort_values(by=["Product ID", "Week_Ending"]).reset_index(drop=True)

    if product_mapping is None:
        product_mapping = build_product_mapping(df["Product ID"])

    df["product_code"] = df["Product ID"].astype(str).map(product_mapping).fillna(-1).astype(int)

    grouped = df.groupby("Product ID")["Weekly_Demand"]

    # Prior weekly demand lags (t-1 through t-4)
    for lag in (1, 2, 3, 4):
        df[f"lag_{lag}"] = grouped.shift(lag)

    # Trailing rolling statistics computed strictly from shifted prior weeks
    shifted = grouped.shift(1)
    df["roll_mean_4"] = shifted.groupby(df["Product ID"]).transform(
        lambda s: s.rolling(window=4, min_periods=4).mean()
    )
    df["roll_std_4"] = shifted.groupby(df["Product ID"]).transform(
        lambda s: s.rolling(window=4, min_periods=4).std()
    )
    df["roll_mean_8"] = shifted.groupby(df["Product ID"]).transform(
        lambda s: s.rolling(window=8, min_periods=4).mean()
    )

    # Known calendar features
    iso_cal = df["Week_Ending"].dt.isocalendar()
    df["week_of_year"] = iso_cal.week.astype(int)
    df["month"] = df["Week_Ending"].dt.month.astype(int)

    if drop_na:
        df = df.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)

    return df, product_mapping


def chronological_week_split(
    df: pd.DataFrame,
    train_ratio: float = 0.80,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object]]:
    """
    Split a product-week DataFrame chronologically by unique sorted Week_Ending dates.
    All products belonging to the same week remain on the same side of the split.
    """
    if not (0.0 < train_ratio < 1.0):
        raise ValueError("train_ratio must be strictly between 0 and 1.")

    unique_weeks = sorted(pd.to_datetime(df["Week_Ending"]).unique())
    if len(unique_weeks) < 2:
        raise ValueError("Need at least 2 unique weeks to perform a chronological split.")

    train_count = int(np.floor(train_ratio * len(unique_weeks)))
    train_count = max(1, min(train_count, len(unique_weeks) - 1))

    train_weeks = unique_weeks[:train_count]
    test_weeks = unique_weeks[train_count:]

    df_dates = pd.to_datetime(df["Week_Ending"])
    train_df = df[df_dates.isin(train_weeks)].copy().reset_index(drop=True)
    test_df = df[df_dates.isin(test_weeks)].copy().reset_index(drop=True)

    split_info = {
        "total_weeks": len(unique_weeks),
        "train_weeks_count": len(train_weeks),
        "test_weeks_count": len(test_weeks),
        "train_start": pd.Timestamp(train_weeks[0]).strftime("%Y-%m-%d"),
        "train_end": pd.Timestamp(train_weeks[-1]).strftime("%Y-%m-%d"),
        "test_start": pd.Timestamp(test_weeks[0]).strftime("%Y-%m-%d"),
        "test_end": pd.Timestamp(test_weeks[-1]).strftime("%Y-%m-%d"),
        "split_date": pd.Timestamp(test_weeks[0]).strftime("%Y-%m-%d"),
        "train_rows": len(train_df),
        "test_rows": len(test_df),
    }

    return train_df, test_df, split_info

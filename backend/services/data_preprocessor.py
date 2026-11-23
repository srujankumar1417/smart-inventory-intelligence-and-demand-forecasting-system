from typing import List, Optional
import pandas as pd


def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Safely clean and preprocess the validated retail sales DataFrame.
    
    Operations:
    1. Deep copy to prevent mutating the original DataFrame.
    2. Convert 'Date' to datetime.
    3. Ensure 'Demand' is numeric.
    4. Clean string/identifier columns.
    5. Sort chronologically by Date, Store ID (if available), and Product ID.
    
    Returns:
        Preprocessed pandas DataFrame ready for downstream aggregation.
    """
    if df is None or df.empty:
        raise ValueError("Cannot preprocess an empty or None DataFrame.")

    # Create deep copy
    clean_df = df.copy()

    # 1. Type conversions
    clean_df["Date"] = pd.to_datetime(clean_df["Date"], errors="raise")
    clean_df["Demand"] = pd.to_numeric(clean_df["Demand"], errors="raise")

    # 2. Clean string columns if present
    for col in ["Product ID", "Store ID", "Category", "Region", "Weather Condition", "Seasonality"]:
        if col in clean_df.columns:
            clean_df[col] = clean_df[col].astype(str).str.strip()

    # 3. Deterministic chronological sorting
    sort_columns = [col for col in ["Date", "Store ID", "Product ID"] if col in clean_df.columns]
    clean_df = clean_df.sort_values(by=sort_columns).reset_index(drop=True)

    return clean_df

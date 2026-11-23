import pytest
import pandas as pd

from backend.services.data_preprocessor import preprocess_dataframe


def test_preprocess_dataframe_converts_types():
    """Verify that Date is converted to datetime and Demand is numeric."""
    df = pd.DataFrame({
        "Date": ["2023-01-01", "2023-01-02"],
        "Product ID": ["P0001", "P0001"],
        "Demand": ["100", "200"]
    })
    processed = preprocess_dataframe(df)

    assert pd.api.types.is_datetime64_any_dtype(processed["Date"])
    assert pd.api.types.is_numeric_dtype(processed["Demand"])


def test_preprocess_dataframe_does_not_mutate_original():
    """Verify that the original DataFrame is not modified in-place."""
    df = pd.DataFrame({
        "Date": ["2023-01-02", "2023-01-01"],
        "Product ID": [" P0001 ", "P0001"],
        "Demand": [50, 60]
    })
    original_dates = df["Date"].tolist()
    _ = preprocess_dataframe(df)

    # Original DataFrame must retain its original object types and order
    assert df["Date"].tolist() == original_dates
    assert isinstance(df["Date"].iloc[0], str)


def test_preprocess_dataframe_chronological_sort():
    """Verify that records are sorted chronologically."""
    df = pd.DataFrame({
        "Date": ["2023-01-05", "2023-01-01", "2023-01-03"],
        "Product ID": ["P0001", "P0001", "P0001"],
        "Demand": [10, 20, 30]
    })
    processed = preprocess_dataframe(df)

    expected_dates = pd.to_datetime(["2023-01-01", "2023-01-03", "2023-01-05"])
    assert (processed["Date"].values == expected_dates.values).all()


def test_preprocess_dataframe_strips_whitespace():
    """Verify that whitespace is stripped from string identifiers."""
    df = pd.DataFrame({
        "Date": ["2023-01-01"],
        "Product ID": ["  P0001  "],
        "Store ID": [" S001 "],
        "Demand": [100]
    })
    processed = preprocess_dataframe(df)
    assert processed["Product ID"].iloc[0] == "P0001"
    assert processed["Store ID"].iloc[0] == "S001"

import pytest
import pandas as pd

from backend.services.csv_validator import validate_schema, validate_or_raise
from backend.utils.error_handlers import CSVValidationError


def test_validate_schema_valid_data(sample_valid_df):
    """Test that a compliant DataFrame passes validation."""
    report = validate_schema(sample_valid_df)
    assert report["is_valid"] is True
    assert len(report["errors"]) == 0
    assert report["error_code"] is None
    assert report["metrics"]["total_rows"] == 4
    assert report["metrics"]["unique_products"] == 1


def test_validate_schema_missing_required_column():
    """Test that dropping a required column causes validation to fail with correct error code."""
    df = pd.DataFrame({
        "Date": ["2023-01-01"],
        "Product ID": ["P0001"]
        # Demand is missing
    })
    report = validate_schema(df)
    assert report["is_valid"] is False
    assert report["error_code"] == "MISSING_REQUIRED_COLUMNS"
    assert "Demand" in report["details"]["missing_columns"]

    with pytest.raises(CSVValidationError) as exc_info:
        validate_or_raise(df)
    assert exc_info.value.error_code == "MISSING_REQUIRED_COLUMNS"


def test_validate_schema_empty_dataframe():
    """Test that an empty DataFrame fails validation."""
    df = pd.DataFrame()
    report = validate_schema(df)
    assert report["is_valid"] is False
    assert report["error_code"] == "EMPTY_DATASET"


def test_validate_schema_null_in_required_column():
    """Test that null values in required columns fail validation."""
    df = pd.DataFrame({
        "Date": ["2023-01-01", "2023-01-02"],
        "Product ID": ["P0001", None],
        "Demand": [50, 60]
    })
    report = validate_schema(df)
    assert report["is_valid"] is False
    assert report["error_code"] == "NULL_VALUES_IN_REQUIRED_COLUMNS"


def test_validate_schema_invalid_dates():
    """Test that unparseable date strings fail validation."""
    df = pd.DataFrame({
        "Date": ["not-a-real-date", "2023-01-02"],
        "Product ID": ["P0001", "P0001"],
        "Demand": [50, 60]
    })
    report = validate_schema(df)
    assert report["is_valid"] is False
    assert report["error_code"] == "INVALID_DATE_VALUES"
    assert report["details"]["invalid_dates_count"] == 1


def test_validate_schema_non_numeric_demand():
    """Test that string or non-numeric Demand values fail validation."""
    df = pd.DataFrame({
        "Date": ["2023-01-01", "2023-01-02"],
        "Product ID": ["P0001", "P0001"],
        "Demand": ["invalid_number", 60]
    })
    report = validate_schema(df)
    assert report["is_valid"] is False
    assert report["error_code"] == "INVALID_DEMAND_VALUES"


def test_validate_schema_negative_demand():
    """Test that negative Demand values fail validation."""
    df = pd.DataFrame({
        "Date": ["2023-01-01", "2023-01-02"],
        "Product ID": ["P0001", "P0001"],
        "Demand": [100, -5]
    })
    report = validate_schema(df)
    assert report["is_valid"] is False
    assert report["error_code"] == "NEGATIVE_DEMAND_VALUES"
    assert report["details"]["negative_demand_count"] == 1


def test_validate_schema_blank_product_id():
    """Test that whitespace-only or empty product IDs fail validation."""
    df = pd.DataFrame({
        "Date": ["2023-01-01", "2023-01-02"],
        "Product ID": ["P0001", "   "],
        "Demand": [100, 50]
    })
    report = validate_schema(df)
    assert report["is_valid"] is False
    assert report["error_code"] == "INVALID_PRODUCT_IDENTIFIERS"


def test_validate_schema_duplicates_reported_as_warnings():
    """Test that duplicate rows produce warnings but do not invalidate schema."""
    df = pd.DataFrame({
        "Date": ["2023-01-01", "2023-01-01"],
        "Store ID": ["S001", "S001"],
        "Product ID": ["P0001", "P0001"],
        "Demand": [50, 50]
    })
    report = validate_schema(df)
    assert report["is_valid"] is True
    assert report["duplicate_rows"] == 1
    assert any("duplicate" in w.lower() for w in report["warnings"])

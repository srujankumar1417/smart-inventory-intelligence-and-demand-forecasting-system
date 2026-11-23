from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from backend.config import Config
from backend.utils.error_handlers import CSVValidationError


def validate_schema(
    df: pd.DataFrame,
    required_columns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Rigorously validate the dataset schema and data quality constraints.

    Returns:
        Structured dictionary detailing validation status, errors, warnings, and metrics.
    """
    if required_columns is None:
        required_columns = Config.REQUIRED_COLUMNS

    errors: List[str] = []
    warnings: List[str] = []
    error_code: str = "CSV_VALIDATION_ERROR"
    details: Dict[str, Any] = {}

    # 1. Non-empty check
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or len(df) == 0:
        errors.append("Dataset is empty or invalid.")
        return {
            "is_valid": False,
            "error_code": "EMPTY_DATASET",
            "message": "Dataset contains no records.",
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    present_columns = df.columns.tolist()

    # 2. Required columns presence
    missing_required = [col for col in required_columns if col not in present_columns]
    if missing_required:
        errors.append(f"Missing required columns: {missing_required}")
        details["missing_columns"] = missing_required
        return {
            "is_valid": False,
            "error_code": "MISSING_REQUIRED_COLUMNS",
            "message": f"The uploaded CSV is missing required columns: {', '.join(missing_required)}",
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    # 3. Check for null values in required columns
    null_counts = {col: int(df[col].isna().sum()) for col in required_columns}
    cols_with_nulls = {col: count for col, count in null_counts.items() if count > 0}
    if cols_with_nulls:
        errors.append(f"Null values found in required columns: {cols_with_nulls}")
        error_code = "NULL_VALUES_IN_REQUIRED_COLUMNS"
        details["null_counts"] = cols_with_nulls

    # 4. Validate Date values
    temp_dates = pd.to_datetime(df["Date"], errors="coerce")
    invalid_dates_count = int(temp_dates.isna().sum())
    if invalid_dates_count > 0:
        errors.append(f"Found {invalid_dates_count} invalid or unparseable date values.")
        error_code = "INVALID_DATE_VALUES"
        details["invalid_dates_count"] = invalid_dates_count

    # 5. Validate Demand values (numeric & non-negative)
    temp_demand = pd.to_numeric(df["Demand"], errors="coerce")
    non_numeric_demand_count = int(temp_demand.isna().sum())
    if non_numeric_demand_count > 0:
        errors.append(f"Found {non_numeric_demand_count} non-numeric Demand values.")
        error_code = "INVALID_DEMAND_VALUES"
        details["non_numeric_demand_count"] = non_numeric_demand_count
    else:
        negative_demand_count = int((temp_demand < 0).sum())
        if negative_demand_count > 0:
            errors.append(f"Found {negative_demand_count} negative Demand values. Demand must be >= 0.")
            error_code = "NEGATIVE_DEMAND_VALUES"
            details["negative_demand_count"] = negative_demand_count

    # 6. Validate Product ID values (non-blank strings)
    blank_products = int((df["Product ID"].astype(str).str.strip() == "").sum())
    if blank_products > 0:
        errors.append(f"Found {blank_products} blank or empty Product ID values.")
        error_code = "INVALID_PRODUCT_IDENTIFIERS"
        details["blank_product_ids"] = blank_products

    # 7. Check duplicates (reported as findings/warnings)
    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows > 0:
        warnings.append(f"Encountered {duplicate_rows} exact duplicate rows in the dataset.")

    duplicate_triplets = 0
    if "Store ID" in df.columns:
        duplicate_triplets = int(df.duplicated(subset=["Product ID", "Store ID", "Date"]).sum())
        if duplicate_triplets > 0:
            warnings.append(f"Encountered {duplicate_triplets} duplicate observations for (Product ID, Store ID, Date).")

    # 8. Check presence of other expected columns
    missing_expected = [col for col in Config.EXPECTED_COLUMNS if col not in present_columns]
    if missing_expected:
        warnings.append(f"Dataset does not contain some optional/expected columns: {missing_expected}")

    is_valid = len(errors) == 0

    return {
        "is_valid": is_valid,
        "error_code": None if is_valid else error_code,
        "message": "Dataset schema and data constraints passed." if is_valid else errors[0],
        "errors": errors,
        "warnings": warnings,
        "details": details,
        "present_columns": present_columns,
        "missing_columns": missing_required,
        "null_counts": null_counts,
        "duplicate_rows": duplicate_rows,
        "duplicate_triplets": duplicate_triplets,
        "invalid_dates_count": invalid_dates_count,
        "metrics": {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "unique_products": int(df["Product ID"].nunique()),
            "unique_stores": int(df["Store ID"].nunique()) if "Store ID" in df.columns else 1,
            "unique_dates": int(temp_dates.nunique()) if invalid_dates_count == 0 else 0
        }
    }


def validate_or_raise(
    df: pd.DataFrame,
    required_columns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Validate the DataFrame and raise CSVValidationError if constraints fail.
    """
    report = validate_schema(df, required_columns=required_columns)
    if not report["is_valid"]:
        raise CSVValidationError(
            message=report["message"],
            error_code=report.get("error_code", "CSV_VALIDATION_ERROR"),
            details=report.get("details", {})
        )
    return report

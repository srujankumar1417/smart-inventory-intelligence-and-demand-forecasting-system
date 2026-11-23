import pytest
import pandas as pd

from backend.services.weekly_aggregator import aggregate_weekly_demand, build_processing_summary


def test_aggregate_weekly_demand_sums_across_stores():
    """Verify that demand on the same date/week across different stores is summed."""
    df = pd.DataFrame({
        "Date": pd.to_datetime(["2023-01-02", "2023-01-02", "2023-01-03"]),  # Monday, Monday, Tuesday
        "Store ID": ["S001", "S002", "S001"],
        "Product ID": ["P0001", "P0001", "P0001"],
        "Demand": [100, 150, 50]
    })
    weekly = aggregate_weekly_demand(df)

    assert len(weekly) == 1
    assert weekly["Product ID"].iloc[0] == "P0001"
    assert weekly["Weekly_Demand"].iloc[0] == 300  # 100 + 150 + 50
    # 2023-01-02 is Monday, ending Sunday is 2023-01-08
    assert weekly["Week_Ending"].iloc[0] == pd.Timestamp("2023-01-08")


def test_aggregate_weekly_demand_w_sun_convention():
    """Verify that all output Week_Ending dates fall on Sundays."""
    df = pd.DataFrame({
        "Date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-09", "2023-01-15"]),
        "Product ID": ["P0001", "P0001", "P0001", "P0001"],
        "Demand": [10, 20, 30, 40]
    })
    weekly = aggregate_weekly_demand(df)

    for week_ending in weekly["Week_Ending"]:
        assert week_ending.day_name() == "Sunday"


def test_aggregate_weekly_demand_no_zero_filling():
    """Verify that missing product-week intervals are not silently zero-filled."""
    df = pd.DataFrame({
        "Date": pd.to_datetime(["2023-01-01", "2023-01-22"]),  # Week 1 and Week 4, weeks 2 & 3 missing
        "Product ID": ["P0001", "P0001"],
        "Demand": [100, 200]
    })
    weekly = aggregate_weekly_demand(df)

    # Should only have 2 records, NOT 4 records with zeros
    assert len(weekly) == 2
    assert weekly["Weekly_Demand"].tolist() == [100, 200]


def test_build_processing_summary():
    """Verify that build_processing_summary returns the required schema and notes."""
    raw_df = pd.DataFrame({
        "Date": ["2023-01-01", "2023-01-02"],
        "Store ID": ["S001", "S001"],
        "Product ID": ["P0001", "P0001"],
        "Demand": [50, 60]
    })
    proc_df = raw_df.copy()
    proc_df["Date"] = pd.to_datetime(proc_df["Date"])
    weekly = aggregate_weekly_demand(proc_df)

    summary = build_processing_summary(raw_df, proc_df, weekly)

    assert "data_summary" in summary
    assert "weekly_schema" in summary
    assert "notes" in summary
    assert summary["weekly_schema"] == ["Product ID", "Week_Ending", "Weekly_Demand"]
    assert summary["data_summary"]["total_records"] == 2
    assert summary["data_summary"]["unique_products"] == 1

import io
import pytest


def test_serve_frontend_root(client):
    """GET / must serve the integrated Smartventory web UI."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Smartventory" in resp.data
    assert b"/api/analyze" in resp.data


def test_analyze_demo_end_to_end_and_forecast_and_recommendations(client, sales_data_csv_path):
    """
    Test POST /api/analyze (use_demo=True) -> POST /api/forecast (1..12 weeks) -> POST /api/recommendations.
    """
    # 1. Analyze demo dataset (sales_data.csv)
    resp = client.post("/api/analyze", json={"use_demo": True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    dataset_id = data["dataset_id"]
    assert dataset_id
    assert data["meta"]["total_rows"] == 76000
    assert data["meta"]["unique_products"] == 20
    assert data["meta"]["unique_weeks"] == 110
    assert data["meta"]["verified_opening_stock_semantics"] is True
    assert data["meta"]["model_info"]["model_ready"] is True
    assert data["meta"]["model_info"]["conformal_1w_half_width"] is not None
    assert len(data["products"]) == 20
    assert len(data["recommendations"]) == 20

    # 2. Forecast 4 weeks for P0001
    fc_resp = client.post("/api/forecast", json={
        "dataset_id": dataset_id,
        "product_id": "P0001",
        "horizon_weeks": 4,
    })
    assert fc_resp.status_code == 200
    fc_data = fc_resp.get_json()
    assert fc_data["status"] == "success"
    assert fc_data["horizon_weeks"] == 4
    assert len(fc_data["forecast"]) == 4
    assert fc_data["has_calibrated_intervals"] is True
    assert all(pt["lower_bound"] is not None and pt["upper_bound"] is not None for pt in fc_data["forecast"])

    # 3. Invalid horizon (> 12 or bool) rejected cleanly
    bad_fc = client.post("/api/forecast", json={
        "dataset_id": dataset_id,
        "product_id": "P0001",
        "horizon_weeks": 26,
    })
    assert bad_fc.status_code == 400
    assert bad_fc.get_json()["error_code"] == "INVALID_HORIZON"

    bad_bool_fc = client.post("/api/forecast", json={
        "dataset_id": dataset_id,
        "product_id": "P0001",
        "horizon_weeks": True,
    })
    assert bad_bool_fc.status_code == 400
    assert bad_bool_fc.get_json()["error_code"] == "INVALID_HORIZON"

    # 4. Recalculate recommendations with updated policy assumptions
    rec_resp = client.post("/api/recommendations", json={
        "dataset_id": dataset_id,
        "lead_time_weeks": 2.0,
        "safety_stock_weeks": 1.0,
    })
    assert rec_resp.status_code == 200
    rec_data = rec_resp.get_json()
    assert len(rec_data["recommendations"]) == 20
    assert rec_data["policy"]["lead_time_weeks"] == 2.0


def test_analyze_minimal_3_column_csv_upload_graceful(client):
    """
    A short 5-week 3-column CSV (Date, Product ID, Demand) must analyze cleanly
    without fabricating Random Forest metrics or inventory data.
    """
    csv_bytes = (
        "Date,Product ID,Demand\n"
        "2024-01-01,P0001,100\n"
        "2024-01-08,P0001,110\n"
        "2024-01-15,P0001,120\n"
        "2024-01-22,P0001,130\n"
        "2024-01-29,P0001,140\n"
    ).encode("utf-8")

    resp = client.post(
        "/api/analyze",
        data={"file": (io.BytesIO(csv_bytes), "minimal.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["meta"]["model_info"]["model_ready"] is False
    assert data["meta"]["model_info"]["mae"] is None
    assert data["meta"]["has_inventory_data"] is False
    assert data["recommendations"] == []

    # Forecast still works using transparent historical average fallback
    fc_resp = client.post("/api/forecast", json={
        "dataset_id": data["dataset_id"],
        "product_id": "P0001",
        "horizon_weeks": 2,
    })
    assert fc_resp.status_code == 200
    assert len(fc_resp.get_json()["forecast"]) == 2
    assert fc_resp.get_json()["has_calibrated_intervals"] is False


def test_analyze_rejects_bad_file_and_missing_columns(client):
    """Verify consistent structured error handling on /api/analyze."""
    bad_ext = client.post(
        "/api/analyze",
        data={"file": (io.BytesIO(b"abc"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert bad_ext.status_code == 415
    assert bad_ext.get_json()["error_code"] == "UNSUPPORTED_MEDIA_TYPE"

    missing_col = client.post(
        "/api/analyze",
        data={"file": (io.BytesIO(b"Date,Product ID\n2024-01-01,P1\n"), "bad.csv")},
        content_type="multipart/form-data",
    )
    assert missing_col.status_code == 400
    assert missing_col.get_json()["error_code"] == "MISSING_REQUIRED_COLUMNS"

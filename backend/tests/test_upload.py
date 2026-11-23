import io
import pytest


def test_upload_csv_success(client, sample_valid_csv_bytes):
    """Test successful CSV upload returns status 200 and structured processing summary."""
    data = {
        "file": (io.BytesIO(sample_valid_csv_bytes), "sample_sales.csv")
    }
    response = client.post("/api/upload", data=data, content_type="multipart/form-data")

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert "data_summary" in json_data
    assert json_data["data_summary"]["total_records"] == 4
    assert json_data["data_summary"]["unique_products"] == 2
    assert "weekly_schema" in json_data
    assert json_data["weekly_schema"] == ["Product ID", "Week_Ending", "Weekly_Demand"]


def test_upload_csv_missing_file_field(client):
    """Test request without 'file' part returns status 400 with MISSING_FILE_FIELD."""
    response = client.post("/api/upload", data={}, content_type="multipart/form-data")

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["status"] == "error"
    assert json_data["error_code"] == "MISSING_FILE_FIELD"


def test_upload_csv_empty_filename(client):
    """Test upload with empty filename returns status 400 with EMPTY_FILENAME."""
    data = {
        "file": (io.BytesIO(b"dummy,content"), "")
    }
    response = client.post("/api/upload", data=data, content_type="multipart/form-data")

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["status"] == "error"
    assert json_data["error_code"] == "EMPTY_FILENAME"


def test_upload_csv_unsupported_file_extension(client):
    """Test upload with non-csv file extension returns status 415."""
    data = {
        "file": (io.BytesIO(b"dummy content"), "document.pdf")
    }
    response = client.post("/api/upload", data=data, content_type="multipart/form-data")

    assert response.status_code == 415
    json_data = response.get_json()
    assert json_data["status"] == "error"
    assert json_data["error_code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_csv_empty_file_content(client):
    """Test upload of 0-byte file returns status 400."""
    data = {
        "file": (io.BytesIO(b""), "empty.csv")
    }
    response = client.post("/api/upload", data=data, content_type="multipart/form-data")

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["status"] == "error"


def test_upload_csv_missing_required_column(client):
    """Test upload of CSV missing 'Demand' returns status 400 with MISSING_REQUIRED_COLUMNS."""
    invalid_csv = b"Date,Product ID\n2023-01-01,P0001\n"
    data = {
        "file": (io.BytesIO(invalid_csv), "missing_demand.csv")
    }
    response = client.post("/api/upload", data=data, content_type="multipart/form-data")

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["status"] == "error"
    assert json_data["error_code"] == "MISSING_REQUIRED_COLUMNS"
    assert "Demand" in json_data["details"]["missing_columns"]


def test_health_check_endpoint(client):
    """Test the /api/health endpoint returns 200 and healthy status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "healthy"

from flask import Blueprint, jsonify, request

from backend.config import Config
from backend.services.csv_loader import load_csv
from backend.services.csv_validator import validate_or_raise
from backend.services.data_preprocessor import preprocess_dataframe
from backend.services.weekly_aggregator import aggregate_weekly_demand, build_processing_summary
from backend.utils.error_handlers import (
    CSVValidationError,
    UnsupportedFileTypeError,
)

upload_bp = Blueprint("upload", __name__, url_prefix="/api")


@upload_bp.route("/upload", methods=["POST"])
def upload_csv():
    """
    Handle CSV upload, validate schema & quality, preprocess data, and aggregate weekly demand.
    
    Accepts:
        multipart/form-data with file field 'file'
        
    Returns:
        JSON response with status, summary metrics, and weekly schema.
    """
    # 1. Verify file part exists
    if "file" not in request.files:
        raise CSVValidationError(
            message="No file part in the request. Expected multipart field name 'file'.",
            error_code="MISSING_FILE_FIELD",
            details={"expected_field": "file"}
        )

    file = request.files["file"]

    # 2. Verify filename is present
    if not file or not file.filename or file.filename.strip() == "":
        raise CSVValidationError(
            message="No file selected or empty filename provided.",
            error_code="EMPTY_FILENAME",
            details={}
        )

    # 3. Verify file extension
    filename = file.filename.lower()
    allowed_exts = tuple(f".{ext}" for ext in Config.ALLOWED_EXTENSIONS)
    if not filename.endswith(allowed_exts):
        raise UnsupportedFileTypeError(
            message=f"Unsupported file type for '{file.filename}'. Only CSV files (.csv) are accepted.",
            details={"allowed_extensions": list(Config.ALLOWED_EXTENSIONS)}
        )

    # 4. Read CSV safely into DataFrame
    raw_df = load_csv(file)

    # 5. Validate schema and constraints (raises CSVValidationError on failure)
    validate_or_raise(raw_df)

    # 6. Preprocess and clean data
    processed_df = preprocess_dataframe(raw_df)

    # 7. Aggregate to weekly demand per product across stores
    weekly_df = aggregate_weekly_demand(processed_df)

    # 8. Construct structured summary
    summary = build_processing_summary(raw_df, processed_df, weekly_df)

    response_payload = {
        "status": "success",
        "message": "Dataset validated and processed successfully.",
        **summary
    }

    return jsonify(response_payload), 200


@upload_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint to verify backend status."""
    return jsonify({
        "status": "healthy",
        "service": "Smartventory Data Pipeline API",
        "version": "1.0.0"
    }), 200

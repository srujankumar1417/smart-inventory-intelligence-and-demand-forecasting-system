import os
from flask import Blueprint, current_app, jsonify, request, send_from_directory

from backend.config import Config
from backend.services.csv_loader import load_csv
from backend.services.pipeline_service import (
    load_demo_dataframe,
    recalculate_recommendations_for_session,
    run_full_analysis_pipeline,
    run_product_forecast,
)
from backend.utils.error_handlers import (
    CSVValidationError,
    UnsupportedFileTypeError,
)


analysis_bp = Blueprint("analysis", __name__)


def _parse_non_negative_float(raw_val, default_val: float, field_name: str) -> float:
    if raw_val is None or raw_val == "":
        return default_val
    try:
        val = float(raw_val)
    except (TypeError, ValueError):
        raise CSVValidationError(
            message=f"Parameter '{field_name}' must be a valid number.",
            error_code="INVALID_POLICY_PARAMETERS",
        )
    if val < 0:
        raise CSVValidationError(
            message=f"Parameter '{field_name}' must be >= 0.",
            error_code="INVALID_POLICY_PARAMETERS",
        )
    return val


@analysis_bp.route("/", methods=["GET"])
def serve_frontend():
    """Serve the Smartventory web dashboard directly from Flask."""
    static_dir = os.path.join(current_app.root_path, "static")
    return send_from_directory(static_dir, "index.html")


@analysis_bp.route("/api/analyze", methods=["POST"])
def analyze_dataset():
    """
    Full Part 2/3 pipeline endpoint:
    - Accepts multipart/form-data (`file`) OR JSON (`{"use_demo": true}`).
    - Validates CSV, preprocesses, aggregates W-SUN demand, fits Random Forest,
      calibrates split-conformal intervals, analyzes inventory, and returns recommendations.
    """
    if request.content_type and "multipart/form-data" in request.content_type:
        if "file" not in request.files:
            raise CSVValidationError(
                message="No file part in the request. Expected multipart field name 'file'.",
                error_code="MISSING_FILE_FIELD",
                details={"expected_field": "file"},
            )
        file = request.files["file"]
        if not file or not file.filename or file.filename.strip() == "":
            raise CSVValidationError(
                message="No file selected or empty filename provided.",
                error_code="EMPTY_FILENAME",
            )
        allowed_exts = tuple(f".{ext}" for ext in Config.ALLOWED_EXTENSIONS)
        if not file.filename.lower().endswith(allowed_exts):
            raise UnsupportedFileTypeError(
                message=f"Unsupported file type for '{file.filename}'. Only CSV files (.csv) are accepted.",
                details={"allowed_extensions": list(Config.ALLOWED_EXTENSIONS)},
            )
        lead_time = _parse_non_negative_float(request.form.get("lead_time_weeks"), 1.0, "lead_time_weeks")
        safety_stock = _parse_non_negative_float(request.form.get("safety_stock_weeks"), 0.5, "safety_stock_weeks")
        raw_df = load_csv(file)
        result = run_full_analysis_pipeline(
            raw_df=raw_df,
            file_name=file.filename,
            source_type="uploaded",
            lead_time_weeks=lead_time,
            safety_stock_weeks=safety_stock,
        )
        return jsonify(result), 200

    # JSON body: demo mode
    payload = request.get_json(silent=True) or {}
    if payload.get("use_demo"):
        lead_time = _parse_non_negative_float(payload.get("lead_time_weeks"), 1.0, "lead_time_weeks")
        safety_stock = _parse_non_negative_float(payload.get("safety_stock_weeks"), 0.5, "safety_stock_weeks")
        workspace_root = os.path.abspath(os.path.join(current_app.root_path, ".."))
        raw_df, demo_name = load_demo_dataframe(workspace_root)
        result = run_full_analysis_pipeline(
            raw_df=raw_df,
            file_name=demo_name,
            source_type="demo",
            lead_time_weeks=lead_time,
            safety_stock_weeks=safety_stock,
        )
        return jsonify(result), 200

    raise CSVValidationError(
        message="Expected multipart CSV upload (`file`) or JSON `{\"use_demo\": true}`.",
        error_code="INVALID_ANALYZE_REQUEST",
    )


@analysis_bp.route("/api/forecast", methods=["POST"])
def forecast_product():
    """
    Generate 1..12 week recursive forecast with step-calibrated intervals for a selected product.
    """
    payload = request.get_json(silent=True) or {}
    dataset_id = payload.get("dataset_id")
    product_id = payload.get("product_id")
    horizon_raw = payload.get("horizon_weeks", 4)

    if not product_id:
        raise CSVValidationError(
            message="Missing required field 'product_id'.",
            error_code="MISSING_PRODUCT_ID",
        )

    if isinstance(horizon_raw, bool):
        raise CSVValidationError(
            message="Field 'horizon_weeks' must be an integer between 1 and 12.",
            error_code="INVALID_HORIZON",
        )

    try:
        horizon_int = int(horizon_raw)
    except (TypeError, ValueError):
        raise CSVValidationError(
            message="Field 'horizon_weeks' must be an integer between 1 and 12.",
            error_code="INVALID_HORIZON",
        )

    try:
        result = run_product_forecast(
            dataset_id=dataset_id,
            product_id=str(product_id),
            horizon_weeks=horizon_int,
        )
    except ValueError as ve:
        raise CSVValidationError(
            message=str(ve),
            error_code="INVALID_HORIZON",
        )

    return jsonify(result), 200


@analysis_bp.route("/api/recommendations", methods=["POST"])
def recalculate_recommendations():
    """
    Recalculate replenishment recommendations for an active dataset session
    with custom lead_time_weeks and safety_stock_weeks assumptions.
    """
    payload = request.get_json(silent=True) or {}
    dataset_id = payload.get("dataset_id")
    lead_time = _parse_non_negative_float(payload.get("lead_time_weeks"), 1.0, "lead_time_weeks")
    safety_stock = _parse_non_negative_float(payload.get("safety_stock_weeks"), 0.5, "safety_stock_weeks")

    result = recalculate_recommendations_for_session(
        dataset_id=dataset_id,
        lead_time_weeks=lead_time,
        safety_stock_weeks=safety_stock,
    )
    return jsonify(result), 200

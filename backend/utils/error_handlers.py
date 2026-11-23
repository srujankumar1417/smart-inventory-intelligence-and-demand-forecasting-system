from typing import Any, Dict, Optional
from flask import Flask, jsonify
from werkzeug.exceptions import RequestEntityTooLarge, BadRequest, UnsupportedMediaType, NotFound


class SmartventoryException(Exception):
    """Base exception for all domain-specific Smartventory errors."""
    def __init__(
        self,
        message: str,
        error_code: str = "APPLICATION_ERROR",
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class CSVLoadError(SmartventoryException):
    """Raised when a CSV stream or file cannot be read."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CSV_LOAD_ERROR",
            status_code=400,
            details=details
        )


class CSVValidationError(SmartventoryException):
    """Raised when a CSV fails schema or data-quality validation."""
    def __init__(self, message: str, error_code: str = "CSV_VALIDATION_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=400,
            details=details
        )


class FileTooLargeError(SmartventoryException):
    """Raised when an uploaded file exceeds the maximum size limit."""
    def __init__(self, message: str = "Uploaded file exceeds maximum allowed size.", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="FILE_TOO_LARGE",
            status_code=413,
            details=details
        )


class UnsupportedFileTypeError(SmartventoryException):
    """Raised when an uploaded file is not an allowed type."""
    def __init__(self, message: str = "Unsupported file type. Only CSV files are accepted.", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="UNSUPPORTED_MEDIA_TYPE",
            status_code=415,
            details=details
        )


def register_error_handlers(app: Flask) -> None:
    """Register centralized JSON error handlers with the Flask application."""

    @app.errorhandler(SmartventoryException)
    def handle_smartventory_exception(error: SmartventoryException):
        response = {
            "status": "error",
            "error_code": error.error_code,
            "message": error.message,
            "details": error.details
        }
        return jsonify(response), error.status_code

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(error: RequestEntityTooLarge):
        response = {
            "status": "error",
            "error_code": "FILE_TOO_LARGE",
            "message": "The uploaded file exceeds the maximum allowed size (16MB).",
            "details": {}
        }
        return jsonify(response), 413

    @app.errorhandler(BadRequest)
    def handle_bad_request(error: BadRequest):
        response = {
            "status": "error",
            "error_code": "BAD_REQUEST",
            "message": str(error.description or "Bad request."),
            "details": {}
        }
        return jsonify(response), 400

    @app.errorhandler(UnsupportedMediaType)
    def handle_unsupported_media_type(error: UnsupportedMediaType):
        response = {
            "status": "error",
            "error_code": "UNSUPPORTED_MEDIA_TYPE",
            "message": "Unsupported media type. Only CSV files are accepted.",
            "details": {}
        }
        return jsonify(response), 415

    @app.errorhandler(NotFound)
    def handle_not_found(error: NotFound):
        response = {
            "status": "error",
            "error_code": "NOT_FOUND",
            "message": "The requested endpoint or resource was not found.",
            "details": {}
        }
        return jsonify(response), 404

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error: Exception):
        app.logger.exception("An unhandled exception occurred: %s", error)
        response = {
            "status": "error",
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected server error occurred while processing the request.",
            "details": {}
        }
        return jsonify(response), 500

class Config:
    """Central configuration for Smartventory Backend."""
    # Maximum upload size: 16 Megabytes
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"csv"}

    # Schema definitions
    REQUIRED_COLUMNS = ["Date", "Product ID", "Demand"]
    EXPECTED_COLUMNS = [
        "Date", "Store ID", "Product ID", "Category", "Region",
        "Inventory Level", "Units Sold", "Units Ordered", "Price",
        "Discount", "Weather Condition", "Promotion", "Competitor Pricing",
        "Seasonality", "Epidemic", "Demand"
    ]

    # Weekly frequency convention: Sunday-ending calendar weeks
    WEEK_FREQUENCY = "W-SUN"

    TESTING = False
    DEBUG = False


class TestingConfig(Config):
    """Configuration for automated test suite."""
    TESTING = True
    DEBUG = True

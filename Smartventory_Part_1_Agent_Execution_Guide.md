# Smartventory --- Part 1 Agent Execution Guide

## Notebook 01 Integration, Data Pipeline Refactoring, and Flask Backend Foundation

**Project:** Smartventory --- Inventory Intelligence & Stock Prediction\
**Phase:** Part 1 of 4\
**Primary objective:** Preserve the work already completed in Notebook
01, convert its reusable data-processing logic into maintainable Python
modules, and expose the resulting pipeline through a Flask backend.

------------------------------------------------------------------------

## 1. Mission and expected outcome

You are working on an existing academic software project called
**Smartventory**. This is not a greenfield project. The project already
has an initial Jupyter notebook containing dataset inspection, weekly
product-level demand aggregation, exploratory data analysis, a four-week
moving-average baseline, chronological evaluation, and baseline metrics.

Your task is to continue from that work rather than replace it.

At the end of this phase, the project should have:

1.  The original Notebook 01 preserved as the record of the initial
    analysis.
2.  Reusable Python modules for CSV loading, schema validation,
    preprocessing, and weekly aggregation.
3.  A Flask backend with a working CSV upload and processing workflow.
4.  A consistent API response format for successful and failed requests.
5.  Automated tests proving that the refactored pipeline behaves
    consistently with Notebook 01.
6.  Clear setup and API documentation.

**Do not implement the Random Forest model, multi-week forecasting,
stockout calculations, replenishment recommendations, React frontend,
authentication, or deployment in this phase.** Those belong to later
project phases.

------------------------------------------------------------------------

## 2. Existing project context --- treat as the source of truth

### 2.1 Existing notebook

The notebook is referred to in the project context as
`NoteBook_01.ipynb`. The actual filename and location may differ.
Inspect the repository and locate the existing notebook before making
changes.

The notebook's completed work includes:

-   Loading and inspecting the original retail CSV dataset.
-   Checking missing values, duplicate rows, date range, and basic data
    validity.
-   Converting dates to datetime and sorting records chronologically.
-   Aggregating daily `Demand` into weekly totals per `Product ID`,
    across all stores.
-   Using Sunday-ending calendar weeks (`W-SUN`).
-   Producing 2,200 product-week records from 20 products and 110 weeks
    in the inspected dataset.
-   Performing exploratory analysis, including weekly demand trends, an
    individual product trend, and demand distribution.
-   Implementing a four-week trailing moving-average baseline separately
    for each product.
-   Using `shift(1)` to prevent current-week leakage.
-   Splitting chronologically by unique week-ending dates, approximately
    80:20.
-   Evaluating 440 test observations with MAE, RMSE, and R².
-   Exporting a weekly product-demand dataset.

Previously reported baseline metrics are:

  Metric                    Reported result
  ----------------------- -----------------
  MAE                                663.63
  RMSE                               880.25
  R²                                -0.1101
  Evaluated predictions                 440

These values are historical reference values, **not values to
hardcode**. Re-run the notebook or inspect its saved outputs if
verification is needed. If results differ because of code, data, library
versions, or execution changes, report the actual results and explain
the difference.

The original dataset was previously inspected as containing 76,000 rows
and 16 columns, with 760 unique dates, 5 stores, 20 products, 5
categories, and 4 regions. It had no missing values or duplicate rows in
that inspection. The dataset covers 2022-01-01 through 2024-01-30.
Recheck the actual file before relying on these figures.

### 2.2 Dataset columns

The known dataset schema is:

-   `Date`
-   `Store ID`
-   `Product ID`
-   `Category`
-   `Region`
-   `Inventory Level`
-   `Units Sold`
-   `Units Ordered`
-   `Price`
-   `Discount`
-   `Weather Condition`
-   `Promotion`
-   `Competitor Pricing`
-   `Seasonality`
-   `Epidemic`
-   `Demand`

The forecasting target established in Notebook 01 is `Demand`,
aggregated into weekly product-level totals.

### 2.3 Forecasting design decisions that must remain unchanged in Part 1

-   Forecasting grain: **one record per product per calendar week**.
-   Product grouping: `Product ID`.
-   Demand aggregation: sum of daily `Demand`.
-   Store handling: aggregate across all stores; do not create
    store-product forecasts in this phase.
-   Week convention: Sunday-ending weeks (`W-SUN`).
-   Partial first and last calendar weeks must be handled transparently.
-   Do not silently fill missing product-week combinations with zero. A
    missing record is not automatically proof of zero demand.
-   Do not introduce Random Forest or change the modelling target in
    this phase.
-   Do not change the existing moving-average baseline logic while
    refactoring it.

------------------------------------------------------------------------

## 3. First action: inspect before editing

Before writing code:

1.  Inspect the repository root and existing directory structure.
2.  Locate `NoteBook_01.ipynb`.
3.  Locate the original CSV, expected to be `sales_data.csv` or an
    equivalent existing file.
4.  Identify the notebook's actual input and output paths.
5.  Inspect the notebook cells and saved outputs.
6.  Identify any existing Python scripts, requirements files, README, or
    backend code.
7.  Record the current project state in a short implementation note.

Do not assume paths from this guide are exact. Adapt to the repository's
actual structure.

**Do not overwrite, rename, delete, or materially rewrite the original
notebook or source CSV.** If a notebook correction is necessary, explain
why and preserve a copy before changing it.

Do not create duplicate project folders or move existing project files
unless there is a clear reason.

------------------------------------------------------------------------

## 4. Target architecture

Use the existing project structure where practical. If no backend
structure exists, create a clean structure similar to this:

``` text
SmartVentory/
│
├── notebooks/
│   └── NoteBook_01.ipynb
│
├── data/
│   └── sample_dataset.csv
│
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── requirements.txt
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   └── upload_routes.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── csv_loader.py
│   │   ├── csv_validator.py
│   │   ├── data_preprocessor.py
│   │   └── weekly_aggregator.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   └── error_handlers.py
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_upload.py
│       ├── test_validation.py
│       ├── test_preprocessing.py
│       └── test_weekly_aggregation.py
│
├── README.md
└── .gitignore
```

This is a proposed structure, not a reason to reorganize a working
repository unnecessarily. Keep notebook experiments separate from
production-style application code.

### Module responsibilities

  -----------------------------------------------------------------------
  Module                              Responsibility
  ----------------------------------- -----------------------------------
  `app.py`                            Create/configure the Flask
                                      application and register routes

  `config.py`                         Central configuration, upload
                                      limits, allowed file types

  `csv_loader.py`                     Read uploaded CSV bytes/file stream
                                      into a DataFrame

  `csv_validator.py`                  Validate schema and data-quality
                                      constraints

  `data_preprocessor.py`              Apply safe, documented data type
                                      and cleaning operations

  `weekly_aggregator.py`              Aggregate demand per product per
                                      Sunday-ending week

  `upload_routes.py`                  HTTP endpoints and request/response
                                      handling

  `error_handlers.py`                 Consistent application-level error
                                      responses

  `tests/`                            Automated tests for the pipeline
                                      and API
  -----------------------------------------------------------------------

Keep business logic out of Flask route functions. Routes should
orchestrate service functions, not contain the full processing
implementation.

------------------------------------------------------------------------

## 5. Workstream A --- extract reusable logic from Notebook 01

Review Notebook 01 and identify code that is reusable outside the
notebook.

Refactor only the logic needed for the backend pipeline:

1.  CSV reading.
2.  Required-column validation.
3.  Data type validation and conversion.
4.  Data-quality checks.
5.  Date normalization and chronological sorting.
6.  Weekly product-level demand aggregation.

Keep notebook-only content such as plots, exploratory commentary, model
evaluation visualizations, and experimentation in the notebook. Do not
force EDA into the backend.

### Required function design

Use clear functions with type hints and docstrings. Exact names may be
adjusted to fit the codebase, but keep responsibilities separated.

Suggested interfaces:

``` python
def load_csv(file_stream) -> pd.DataFrame:
    """Read a CSV upload into a DataFrame and raise a clear error if unreadable."""
```

``` python
def validate_schema(df: pd.DataFrame) -> dict:
    """Check required columns and return a structured validation report."""
```

``` python
def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply documented type conversions and safe preprocessing."""
```

``` python
def aggregate_weekly_demand(df: pd.DataFrame) -> pd.DataFrame:
    """Return weekly demand totals grouped by Product ID and W-SUN week."""
```

``` python
def build_processing_summary(
    original_df: pd.DataFrame,
    processed_df: pd.DataFrame,
    weekly_df: pd.DataFrame
) -> dict:
    """Build a JSON-serializable summary of the processing results."""
```

Use exceptions with clear messages for unrecoverable problems. Avoid
returning ambiguous `None` values for failed operations.

### Preserve existing logic

-   Read the actual notebook implementation before refactoring.
-   Preserve the same weekly grouping and sum operation.
-   Preserve the `W-SUN` week convention.
-   Preserve aggregation across all stores.
-   Preserve partial-week behaviour.
-   Do not add zero-filling for missing product-week combinations.
-   Do not alter the baseline forecasting implementation as part of this
    refactor.
-   Avoid adding transformations that change the meaning of `Demand`.

If the notebook's code has a defect or ambiguity, document it and
explain the proposed correction before changing behaviour.

------------------------------------------------------------------------

## 6. Workstream B --- CSV schema and data validation

Implement validation that is explicit and understandable.

### 6.1 Required versus optional columns

Do not automatically require all 16 known fields without considering
each module's needs.

For the current weekly demand aggregation, the minimum fields are:

-   `Date`
-   `Product ID`
-   `Demand`

Other columns may be required by future inventory analysis or dashboard
functionality. Define the schema in one central place and clearly
classify fields as:

-   Required for the current processing pipeline.
-   Optional for the current pipeline.
-   Expected for later inventory/dashboard functionality.

Do not silently invent missing values for required fields.

### 6.2 Validation checks

At minimum, implement checks for:

-   Missing required columns.
-   Empty CSV.
-   Unreadable or malformed CSV.
-   Invalid date values.
-   Null values in required fields.
-   Invalid numeric values in `Demand`.
-   Non-finite values such as infinity where applicable.
-   Invalid or blank product identifiers.
-   Duplicate records, with a clear policy.
-   Unexpected data types that cannot be safely converted.

Additional checks for inventory and pricing fields may be included when
those fields are present, but do not reject a file for an optional field
unless the current contract explicitly requires it.

### 6.3 Do not silently clean meaningful data

-   Do not replace missing demand with zero automatically.
-   Do not remove duplicate rows without reporting how many were found
    and what policy was applied.
-   Do not clip negative or unusual values without an explicit rule.
-   Do not drop invalid dates silently.
-   Do not assume every extra column is an error.
-   Keep validation findings separate from preprocessing actions.

If invalid rows are rejected or excluded, report counts and reasons. For
the initial implementation, prefer rejecting datasets with invalid
required fields rather than silently modifying them.

------------------------------------------------------------------------

## 7. Workstream C --- preprocessing and weekly aggregation

Implement a deterministic processing sequence:

1.  Load CSV.
2.  Validate required schema.
3.  Validate required-field values and data types.
4.  Convert `Date` to pandas datetime.
5.  Convert `Demand` to a numeric type.
6.  Normalize column names only if this can be done without ambiguity;
    preserve a documented mapping to source names.
7.  Sort chronologically.
8.  Aggregate `Demand` by `Product ID` and Sunday-ending calendar week.
9.  Return the processed weekly DataFrame and a summary.

The weekly output should have a stable schema such as:

  Column            Meaning
  ----------------- -----------------------------------------------
  `Product ID`      Product identifier
  `Week_Ending`     Sunday-ending week date
  `Weekly_Demand`   Sum of daily demand for that product and week

Use the same pandas weekly frequency convention as Notebook 01. Verify
the exact pandas API behaviour in the installed version.

### Partial weeks and missing weeks

-   Preserve partial first and last weeks as the existing notebook does.
-   Include a note in the processing summary that the first/last
    calendar weeks may be partial.
-   Do not manufacture rows for absent product-week combinations.
-   Report observed product count, week count, and product-week record
    count.
-   If useful, report gaps in observed weekly records separately from
    actual zero-demand weeks.

### Output integrity

The aggregation should not mutate the original DataFrame unexpectedly.
Prefer returning a new DataFrame.

Do not overwrite the original CSV. Keep uploads in memory where
practical for this prototype. If temporary storage is necessary, use a
controlled temporary location and clean it up safely.

------------------------------------------------------------------------

## 8. Workstream D --- Flask backend and API

Create a Flask application with a simple, testable application factory
if appropriate.

### 8.1 Initial API endpoint

Implement:

`POST /api/upload`

Request: - `multipart/form-data` - File field name: `file` - Accept CSV
only. - Apply a configurable maximum upload size.

Processing sequence: 1. Confirm that the file field exists. 2. Confirm
that a filename is present. 3. Check allowed extension. 4. Read the CSV
safely. 5. Validate the dataset. 6. Preprocess valid data. 7. Aggregate
weekly product demand. 8. Return a JSON summary.

The first version can perform validation and processing within this
single endpoint. Do not create separate public endpoints for every
internal function unless there is a concrete frontend requirement.

### 8.2 Optional summary endpoint

If processing results are retained safely for the current session or
request workflow, consider:

`GET /api/dataset/summary`

Do not introduce a database or global in-memory state merely to support
this endpoint. If no safe persistence/session design exists yet, return
the summary directly from `POST /api/upload` and defer the GET endpoint.

### 8.3 Example successful response

Use this as a shape reference, not as hardcoded data:

``` json
{
  "status": "success",
  "message": "Dataset validated and processed successfully.",
  "data_summary": {
    "total_records": 76000,
    "total_columns": 16,
    "unique_products": 20,
    "unique_stores": 5,
    "weekly_records": 2200,
    "week_start": "2022-01-02",
    "week_end": "2024-02-04"
  },
  "weekly_schema": [
    "Product ID",
    "Week_Ending",
    "Weekly_Demand"
  ],
  "notes": [
    "Weekly demand is aggregated across all stores.",
    "The first and last calendar weeks may be partial."
  ]
}
```

Every returned value must be calculated from the uploaded dataset. Do
not hardcode the example counts or dates.

### 8.4 Error response format

Use a consistent structure, for example:

``` json
{
  "status": "error",
  "error_code": "MISSING_REQUIRED_COLUMNS",
  "message": "The uploaded CSV is missing required columns.",
  "details": {
    "missing_columns": ["Demand"]
  }
}
```

Use appropriate HTTP status codes, such as: - `400` for missing file,
invalid request, or invalid dataset. - `413` for file too large. - `415`
for unsupported media/file type where appropriate. - `500` for
unexpected server errors.

Do not expose stack traces, local file paths, secrets, or internal
implementation details in API responses. Log diagnostic details
server-side.

### 8.5 Security and reliability basics

-   Set a reasonable configurable maximum upload size.
-   Do not trust the uploaded filename or extension alone.
-   Do not execute or evaluate uploaded content.
-   Avoid unsafe path construction from user-provided filenames.
-   Prefer in-memory processing for the initial CSV workflow.
-   If files are written to disk, use safe temporary filenames and
    cleanup.
-   Handle malformed CSVs and unexpected exceptions.
-   Keep debug mode disabled outside local development.
-   Do not add authentication unless required by the current project
    scope.

------------------------------------------------------------------------

## 9. Workstream E --- testing and notebook parity

Testing is a mandatory part of this phase.

### 9.1 Unit tests

Write tests for:

-   CSV loading.
-   Missing required columns.
-   Empty files.
-   Invalid dates.
-   Null required values.
-   Non-numeric demand.
-   Duplicate-row reporting/policy.
-   Preprocessing output types.
-   Weekly aggregation.
-   Partial-week behaviour.
-   Missing product-week intervals not being zero-filled.

### 9.2 API tests

Test:

-   Successful CSV upload.
-   No file submitted.
-   Empty filename.
-   Unsupported file extension.
-   Unreadable/corrupted CSV.
-   Missing required columns.
-   Oversized upload.
-   Unexpected internal exception returns a safe response.

Use Flask's test client and pytest where practical.

### 9.3 Notebook parity test

This is the most important integration check.

Run the refactored backend aggregation on the original dataset and
compare it with the weekly product-demand output produced by Notebook
01.

Compare:

-   Number of product-week records.
-   Product identifiers.
-   Week-ending dates.
-   `Weekly_Demand` values.
-   Total aggregated demand.
-   Minimum and maximum week-ending dates.
-   Partial first and last week behaviour.

Sort both outputs by product and week before comparing. Use exact
equality where the values and data types allow it; otherwise use an
explicitly justified numeric tolerance.

If the outputs differ: 1. Identify the exact rows/columns that differ.
2. Determine whether the cause is a bug, pandas frequency behaviour,
input changes, or a deliberate correction. 3. Do not hide the
discrepancy. 4. Document the resolution. 5. Re-run the tests.

Do not claim parity until the comparison has actually passed.

------------------------------------------------------------------------

## 10. Workstream F --- documentation and handover

Update or create:

### `README.md`

Include: - Project overview. - Part 1 scope. - Prerequisites. -
Environment setup. - Dependency installation. - How to start the Flask
server. - How to run tests. - How to call the upload endpoint. -
Expected CSV schema. - Known limitations.

### API documentation

Document: - Endpoint and HTTP method. - Request content type. - File
field name. - Successful response structure. - Validation error
structure. - HTTP status codes. - Required fields and optional fields.

### Implementation report

At completion, provide a concise report containing: - Files created. -
Existing files modified. - Existing notebook reused. - Functions
extracted from Notebook 01. - API endpoints implemented. - Tests
executed and pass/fail counts. - Notebook parity results. - Actual
dataset counts and date range observed. - Known issues and decisions
deferred to Part 2.

------------------------------------------------------------------------

## 11. Explicit exclusions --- do not expand scope

Do not implement the following in Part 1:

-   Random Forest training or inference.
-   Model serialization with Joblib.
-   User-defined multi-week prediction.
-   Recursive forecasting.
-   Stockout estimation.
-   Safety stock or lead-time calculations.
-   Replenishment quantity recommendations.
-   React/Vite frontend.
-   Plotly dashboard.
-   Authentication or user accounts.
-   Database integration unless the existing project already requires
    it.
-   Cloud deployment.
-   3D animations or decorative UI features.

The existing four-week moving-average baseline remains in Notebook 01 as
an experimental benchmark. It does not need to become a production API
feature in Part 1.

------------------------------------------------------------------------

## 12. Definition of Done --- Part 1 acceptance checklist

Part 1 is complete only when all applicable items below have been
verified.

### Existing work preservation

-   [ ] Original Notebook 01 remains in the project.
-   [ ] Original source CSV remains unchanged.
-   [ ] Existing baseline logic and notebook outputs have not been
    silently replaced.
-   [ ] Notebook-specific EDA remains in the notebook.

### Refactored data pipeline

-   [ ] CSV loading is implemented as reusable code.
-   [ ] Required schema validation is implemented.
-   [ ] Preprocessing is implemented and documented.
-   [ ] Weekly aggregation matches Notebook 01.
-   [ ] `W-SUN` convention is preserved.
-   [ ] Demand is summed by product across stores.
-   [ ] Partial weeks are handled consistently.
-   [ ] Missing product-week rows are not silently zero-filled.

### Flask API

-   [ ] Flask application starts successfully.
-   [ ] `POST /api/upload` accepts valid CSV files.
-   [ ] Invalid uploads return structured errors.
-   [ ] Valid uploads return calculated processing summaries.
-   [ ] Upload limits and safe file handling are implemented.

### Testing and documentation

-   [ ] Unit tests pass.
-   [ ] API tests pass.
-   [ ] Notebook parity test passes or any discrepancy is documented and
    resolved.
-   [ ] README and API instructions are updated.
-   [ ] Completion report is provided.

------------------------------------------------------------------------

## 13. Recommended execution order

Work incrementally. Do not attempt the entire phase in one large
code-generation step.

  -----------------------------------------------------------------------
  Step                    Task                    Completion evidence
  ----------------------- ----------------------- -----------------------
  1                       Inspect repository,     Inspection report and
                          notebook, and dataset   confirmed paths

  2                       Identify reusable       Refactoring map
                          notebook code           

  3                       Create backend          Flask skeleton starts
                          structure and           
                          environment             

  4                       Extract CSV loading and Unit tests pass
                          validation              

  5                       Extract preprocessing   Unit tests pass
                          and weekly aggregation  

  6                       Run notebook parity     Comparison report
                          comparison              

  7                       Implement upload API    API test succeeds

  8                       Add error handling and  Error tests pass
                          upload safeguards       

  9                       Complete test suite     Test summary

  10                      Update documentation    README and completion
                          and handover            report
  -----------------------------------------------------------------------

After each major step, run the relevant tests before proceeding.

------------------------------------------------------------------------

## 14. Final handover to Part 2

At the end of Part 1, hand over a backend pipeline that accepts a user's
retail CSV and produces a validated, preprocessed weekly product-demand
dataset.

**Part 2 will build on this exact pipeline** to:

-   Integrate the Random Forest Regressor developed and evaluated in the
    next modelling notebook.
-   Support user-defined weekly forecasting horizons.
-   Generate product-level demand predictions.
-   Analyze available inventory against forecast demand.
-   Estimate potential stockouts.
-   Calculate replenishment recommendations.

The backend should therefore expose clean, documented service interfaces
that Part 2 can call without reimplementing CSV loading, validation,
preprocessing, or weekly aggregation.

------------------------------------------------------------------------

## 15. Instructions for the agent's final response

When the work is finished, do not simply say "completed." Provide:

1.  A summary of what was implemented.
2.  The final project directory tree.
3.  A list of created and modified files.
4.  The exact command to start the backend.
5.  The exact command to run tests.
6.  The API endpoint and an example request.
7.  Test results with actual pass/fail counts.
8.  Notebook parity results with actual comparison figures.
9.  Any known limitations or unresolved issues.
10. Confirmation that Notebook 01 and the original CSV were preserved.

**Never fabricate test results, dataset statistics, model metrics, or
successful execution claims. If a command could not be run, state that
clearly.**

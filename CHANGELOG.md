# Changelog

All notable changes to ETL Pipeline Builder are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Fixed

- "Row Count After Each Step" chart: steps that share a name (the default pipeline runs `NormalizeText` twice) were drawn in one x slot, so Plotly stacked them into a single bar of 152 rows. Bars are now positioned by execution index with numbered labels (`6. Normalize Text`, `7. Normalize Text`), one bar per executed step. Chart construction moved to `src/charts.py`; ETL transforms and audit records are unchanged.
- Added `tests/test_charts.py` (6 regression tests).
- Updated `screenshots/02_core_feature.png` to show the corrected chart.

---

## [1.0.0] — 2026-06-18

### Added

**Transform pipeline — 10 composable steps (`src/transformer.py`)**
- `NormalizeHeaders` — converts column names to snake_case; strips spaces, hyphens, special characters via regex
- `StripStrings` — strips leading/trailing whitespace from all string cells; preserves NaN values
- `DropDuplicates` — removes exact duplicate rows; accepts optional column subset parameter
- `DropNullRows` — drops rows where any specified column is null or empty string
- `FillNulls` — replaces empty/NaN values with a configured fill value per column
- `NormalizeText` — standardizes string case (title/upper/lower) per specified columns
- `CoerceNumeric` — parses currency and comma-formatted strings (e.g., `$2,278,286`) to float via `pd.to_numeric`
- `CoerceDates` — parses mixed date formats to ISO 8601 YYYY-MM-DD using pandas `format="mixed"`
- `FilterRows` — keeps rows where a column contains (case-insensitive) any value in a provided list
- `RenameColumns` — renames specific columns by a provided mapping dictionary
- `STEP_REGISTRY` — dict mapping display names to `TransformStep` classes; used by the Streamlit UI step selector
- `StepResult` dataclass — `rows_in`, `rows_out`, `duration_ms`, `rows_dropped` property; produced by every `TransformStep.run()` call
- `TransformStep` base dataclass — `apply(df)` pure function + `run(df)` timing wrapper

**Pipeline orchestration (`src/pipeline.py`)**
- `PipelineResult` dataclass — collects `source_path`, `rows_extracted`, `rows_loaded`, `step_log`, `output_df`, `total_duration_ms`, `error`; `summary_df()` returns 6-column audit trail; `success` and `rows_dropped_total` properties
- `run_pipeline(steps, source_path)` — runs Extract → Transform → Load; catches per-step exceptions and logs them without stopping the pipeline; returns `PipelineResult` with `success=False` on extraction failure
- `default_steps()` — 9-step pre-configured pipeline for the sample government contracts dataset: NormalizeHeaders → StripStrings → DropDuplicates → DropNullRows(agency_name) → FillNulls(notes) → NormalizeText(status, vendor) → CoerceNumeric(contract_value) → CoerceDates(start_date, end_date)

**Extract (`src/extractor.py`)**
- `extract_csv(path, encoding)` — reads any CSV with all columns as `str` dtype; strips header whitespace; raises `ValueError` on empty file
- `extract_sample()` — loads bundled `data/sample/sample_raw.csv` via package-relative path

**Load (`src/loader.py`)**
- `load_csv(df, path)` — writes to disk when path provided; returns `BytesIO` for Streamlit downloads
- `load_sqlite(df, db_path, table)` — writes to a SQLite database file on disk
- `load_sqlite_sql(df, table)` — generates portable SQL text dump (`CREATE TABLE` + `INSERT` statements) via in-memory SQLite + `iterdump()`; zero file I/O; returns UTF-8 `BytesIO`
- `load_excel(df, path)` — writes to `.xlsx` format via openpyxl engine; returns `BytesIO` for Streamlit downloads or writes to disk

**CLI entry point (`scripts/run_pipeline.py`)**
- `--input` / `--output` — required CSV input path and output path
- `--sqlite` — optional: write SQLite database to specified path
- `--audit-log` — optional: write step-by-step audit log CSV to specified path

**Streamlit dashboard (`app/main.py`)**
- Pipeline configuration sidebar: source toggle (sample / upload) and step selection toggle (default / custom multiselect via `STEP_REGISTRY`)
- KPI tile strip: Rows Extracted, Rows Loaded, Rows Dropped, Pipeline Steps
- Tab 1 — Run Log: per-step table with rows in/out/dropped/duration; dropped rows highlighted in red; Plotly bar chart of row count after each step (blue for no drops, red for drops)
- Tab 2 — Output Data: cleaned DataFrame preview (500px height)
- Tab 3 — Before vs After: side-by-side raw vs. transformed DataFrames; null/empty count comparison table with Improvement column
- Tab 4 — Download: CSV export, Excel (.xlsx) export, SQL dump export, and Audit Log CSV export
- `@st.cache_data` pipeline caching keyed on raw file bytes

**Sample data (`data/sample/sample_raw.csv`)**
- 90-row synthetic government contracts dataset with intentional data quality issues: mixed-case status values, currency-formatted contract values, mixed date formats, whitespace in vendor names, null and `"N/A"` notes fields, ~10 duplicate rows

**Test suite**
- 69 tests across 4 files: `test_transformer.py` (34 tests — all 10 step types), `test_pipeline.py` (21 tests — pipeline orchestration), `test_extractor.py` (6 tests — extraction), `test_loader.py` (8 tests — CSV/Excel/SQLite load targets)
- All tests runnable with `pytest tests/ -v` from project root with no additional setup

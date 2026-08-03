# Testing — ETL Pipeline Builder

---

## How to Run

```bash
# Full suite with verbose output
pytest tests/ -v

# Single file
pytest tests/test_transformer.py -v
pytest tests/test_pipeline.py -v
pytest tests/test_extractor.py -v
pytest tests/test_loader.py -v

# Single class
pytest tests/test_transformer.py::TestCoerceNumeric -v
```

All tests pass with `pytest tests/ -v` from the project root. No additional setup is required beyond `pip install -r requirements.txt`.

---

## Test Structure

| File | Classes | Tests | Coverage Focus |
|---|---|---|---|
| `test_transformer.py` | 11 | 34 | All 10 step types: correct output values, immutability, edge cases (missing columns, empty inputs, no-op conditions) |
| `test_pipeline.py` | 3 | 21 | Pipeline orchestration: PipelineResult structure, row count consistency, step log integrity, error handling |
| `test_extractor.py` | 2 | 6 | Extraction: return type, column presence, string dtype, explicit path, empty file error |
| `test_loader.py` | 3 | 8 | Load targets: CSV BytesIO + disk, SQLite SQL dump, Excel BytesIO + disk |
| **Total** | **19** | **69** | |

---

## Per-Class Breakdown

### `test_transformer.py`

| Class | Tests | What It Covers |
|---|---|---|
| `TestNormalizeHeaders` | 4 | snake_case conversion; spaces stripped from header names; hyphen-to-underscore; `apply()` does not mutate input |
| `TestStripStrings` | 2 | Leading/trailing whitespace stripped from string cells; `apply()` does not mutate input |
| `TestDropDuplicates` | 3 | Exact duplicate rows removed; no-duplicate input unchanged; `subset` parameter respected |
| `TestDropNullRows` | 3 | Empty string rows dropped; missing column name is a safe no-op; empty column list returns all rows |
| `TestFillNulls` | 2 | Empty string cells filled with configured value; missing column name is a safe no-op |
| `TestNormalizeText` | 4 | Title, upper, and lower case modes; missing column name is a safe no-op |
| `TestCoerceNumeric` | 4 | Currency string (`$1,200,000`) parsed; plain number string parsed; empty string becomes NaN; missing column is safe |
| `TestCoerceDates` | 3 | ISO 8601 date preserved; slash-format (`01/15/2025`) parsed to `2025-01-15`; missing column is safe |
| `TestFilterRows` | 3 | Case-insensitive filter applied; empty `values` list returns all rows; missing column returns all rows |
| `TestRenameColumns` | 2 | Column renamed per mapping; missing mapping key is a safe no-op |
| `TestStepRun` | 4 | `run()` returns `(DataFrame, StepResult)` tuple; `rows_in` equals input length; `duration_ms >= 0`; `rows_dropped` computed correctly |

### `test_pipeline.py`

| Class | Tests | What It Covers |
|---|---|---|
| `TestRunPipeline` | 12 | Returns `PipelineResult`; `success=True` on sample data; `rows_extracted > 0`; `rows_loaded <= rows_extracted`; `step_log` length matches step count; `output_df` is non-empty DataFrame; `total_duration_ms >= 0`; headers normalized after NormalizeHeaders step; `DropDuplicates` reduces row count; empty step list returns raw data; `success=False` on bad path with non-None `error` |
| `TestPipelineResult` | 4 | `rows_dropped_total` computed correctly; `summary_df()` returns DataFrame; expected columns present (Step, Rows In, Rows Out, Rows Dropped, Duration ms); row count in summary matches step log length |
| `TestDefaultSteps` | 5 | Returns list; list is non-empty; pipeline with default steps succeeds; headers are snake_case after default pipeline; `contract_value` column is numeric dtype after default pipeline |

### `test_extractor.py`

| Class | Tests | What It Covers |
|---|---|---|
| `TestExtractSample` | 4 | Returns `pd.DataFrame`; not empty; all columns are `object` (str) dtype; expected column names present |
| `TestExtractCsv` | 2 | Reads from explicit `SAMPLE_PATH` successfully; raises `ValueError` with "empty" on header-only CSV |

### `test_loader.py`

| Class | Tests | What It Covers |
|---|---|---|
| `TestLoadCsv` | 3 | Returns `BytesIO`; `BytesIO` content parses back to correct DataFrame; writes to disk correctly |
| `TestLoadSqliteSql` | 2 | Returns `BytesIO`; content contains `CREATE TABLE` and table name |
| `TestLoadExcel` | 3 | Returns `BytesIO`; `BytesIO` content readable as Excel with correct schema; writes to disk correctly |

---

## Known Gaps

| Gap | Area | Reason | Risk |
|---|---|---|---|
| Streamlit UI layer not tested | `app/main.py` | Excluded by design for all Streamlit projects in this portfolio — Streamlit components require a browser runtime that is not available in a `pytest` context. UI behavior is validated manually. | LOW — all business logic lives in `src/`; the UI is a thin orchestration layer |
| `load_sqlite()` disk write not tested | `src/loader.py` | `load_sqlite()` writes a `.db` binary file to disk. The function is a direct wrapper around `pandas.DataFrame.to_sql()` with a standard `sqlite3` connection, composing two well-tested primitives. The `load_csv()` disk-write test pattern covers the same code path pattern. | LOW — the function body is 3 lines |
| `CoerceDates` ambiguous date format not tested | `src/transformer.py` | Mixed-format ambiguity (e.g., `01/02/2024` — January 2nd vs February 1st) depends on `dayfirst=False` in `pd.to_datetime`. The current test confirms correct parsing of an unambiguous slash-format date; the ambiguous-format behavior is documented as a known limitation. | LOW — behavior is documented in docs/ARCHITECTURE.md; production callers are responsible for dataset-specific `dayfirst` configuration |
| `scripts/run_pipeline.py` CLI not unit-tested | `scripts/` | The CLI script is a thin wrapper that delegates all ETL logic to `run_pipeline()` and loader functions (all tested). Testing the CLI would require subprocess spawning or `argparse`-specific patching with limited coverage benefit. | LOW — all logic tested at the library level |

---

## Testing Philosophy

**Test library code; exclude UI code.** All business logic lives in `src/`. The `app/main.py` Streamlit layer orchestrates calls to `src/` functions and is excluded from automated testing. This is standard practice for Streamlit applications where the UI runtime is not available in a `pytest` context.

**Test real behavior with real data.** No internal library functions are mocked. `TestDefaultSteps.test_pipeline_with_default_steps_succeeds` and `TestRunPipeline.test_success_on_sample` run the full pipeline against `data/sample/sample_raw.csv`. This confirms that the sample data, the path resolution, and the pipeline logic all work end-to-end.

**Test edge cases, not just happy paths.** Every step is tested for its "missing column" behavior (safe no-op), its empty/null input behavior, and at least one boundary condition. The `TestCoerceNumeric` suite tests both valid and invalid inputs; `TestFilterRows` tests the empty-values-list no-op.

**Immutability is a first-class test target.** `TestNormalizeHeaders.test_does_not_mutate` and `TestStripStrings.test_does_not_mutate` verify that the original DataFrame is unchanged after `apply()`. This is the most important invariant in the step design and is worth an explicit test, not just a code comment.

# Architecture — ETL Pipeline Builder

---

## System Overview

ETL Pipeline Builder is a three-stage data processing system: Extract reads a source CSV into a DataFrame, Transform applies a configurable sequence of named steps that clean and reshape the data, and Load writes the result to one or more output formats. A Streamlit UI provides configuration and monitoring; a CLI entry point provides batch automation. All pipeline logic lives in `src/` and is independently executable from either interface.

The central design principle is observability: every transformation step produces a `StepResult` record with row counts and execution time, and the `PipelineResult` aggregates these into a downloadable audit trail.

---

## Pipeline Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│  Input: CSV file path, BytesIO (Streamlit upload), or sample data   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 1 — EXTRACT                    src/extractor.py              │
│                                                                     │
│  extract_csv(path, encoding) / extract_sample()                     │
│  • Reads all columns as str dtype                                   │
│  • Strips column header whitespace                                  │
│  • Raises ValueError on empty file                                  │
│                                                                     │
│  Output: DataFrame (N rows × M cols, all str)                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  raw DataFrame
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 2 — TRANSFORM                  src/transformer.py            │
│                                                                     │
│  For each TransformStep in the pipeline sequence:                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  t0  = perf_counter()                                        │  │
│  │  out = step.apply(df)   ← pure fn; returns new DataFrame     │  │
│  │  ms  = (perf_counter() - t0) × 1000                         │  │
│  │  log.append(StepResult(name, rows_in, rows_out, ms))        │  │
│  │  df  = out                                                   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Default 9-step sequence (tuned for sample_raw.csv):               │
│    1  NormalizeHeaders  → snake_case column names                   │
│    2  StripStrings      → strip leading/trailing whitespace         │
│    3  DropDuplicates    → remove exact duplicate rows               │
│    4  DropNullRows      → drop rows with null/empty agency_name     │
│    5  FillNulls         → replace null notes with "None"            │
│    6  NormalizeText     → title-case status                         │
│    7  NormalizeText     → title-case vendor                         │
│    8  CoerceNumeric     → parse contract_value to float             │
│    9  CoerceDates       → parse dates to ISO 8601 YYYY-MM-DD        │
│                                                                     │
│  Output: cleaned DataFrame + list[StepResult]                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  cleaned DataFrame + step_log
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 3 — LOAD                       src/loader.py                 │
│                                                                     │
│  load_csv(df)        → BytesIO  (UTF-8 CSV; Streamlit download)     │
│  load_excel(df)      → BytesIO  (OOXML .xlsx; openpyxl engine)      │
│  load_sqlite_sql(df) → BytesIO  (CREATE TABLE + INSERT; SQL text)   │
│  load_sqlite(df, p)  → str path (SQLite .db file on disk)           │
│  load_csv(df, path)  → str path (CSV file on disk; CLI use)         │
│                                                                     │
│  Output: file content (BytesIO) or file path (str)                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PipelineResult                       src/pipeline.py               │
│                                                                     │
│  source_path       str                                              │
│  rows_extracted    int                                              │
│  rows_loaded       int                                              │
│  step_log          list[StepResult]                                 │
│  output_df         pd.DataFrame                                     │
│  total_duration_ms float                                            │
│  error             str | None                                       │
│                                                                     │
│  success           → error is None                                  │
│  rows_dropped_total → rows_extracted - rows_loaded                  │
│  summary_df()      → 6-col audit trail DataFrame                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Stage Reference

### Stage 1: Extract

**Input format:** CSV file path (str or Path), BytesIO buffer (Streamlit file_uploader), or no argument (loads bundled sample data).

**Validation:** `df.empty` check — raises `ValueError("Source CSV is empty.")` if the loaded DataFrame has zero rows. Column header whitespace is stripped silently.

**Output:** `pd.DataFrame` with all columns as `object` (str) dtype. Column header whitespace stripped. Original values preserved exactly (no type coercion at this stage).

**Failure mode:** `run_pipeline()` wraps extraction in a try/except. On failure it returns `PipelineResult(success=False, error=str(exc), rows_extracted=0)`. The UI displays `st.error()` and stops.

---

### Stage 2: Transform

Each step is documented below. All steps share the same contract:

- **Pure function:** `apply(df)` returns a new DataFrame; never mutates the input. Enforced by `df = df.copy()` at the start of every method that modifies the frame.
- **Timing wrapper:** `run(df)` calls `apply()`, measures wall-clock time via `time.perf_counter()`, and returns `(out_df, StepResult)`.
- **Error isolation:** `run_pipeline()` catches per-step exceptions, logs them as a `StepResult` with `notes="ERROR: ..."`, and continues to the next step.

| Step | Class | Configurable Parameters | Rows In / Out | Side Effects |
|---|---|---|---|---|
| Normalize Headers | `NormalizeHeaders` | none | preserved | column names changed to snake_case |
| Strip Whitespace | `StripStrings` | none | preserved | leading/trailing whitespace removed from string values |
| Drop Duplicates | `DropDuplicates` | `subset: list[str] \| None` | may reduce | rows with identical values across subset columns removed |
| Drop Null Rows | `DropNullRows` | `columns: list[str]` | may reduce | rows with null or empty string in specified columns removed |
| Fill Nulls | `FillNulls` | `values: dict[str, Any]` | preserved | NaN/empty cells replaced by configured fill values |
| Normalize Text | `NormalizeText` | `columns: list[str]`, `case: str` | preserved | string values case-normalized per column |
| Coerce Numeric | `CoerceNumeric` | `columns: list[str]` | preserved | column dtype changes from str to float64; unparseable → NaN |
| Coerce Dates | `CoerceDates` | `columns: list[str]` | preserved | column type changes from str to str (ISO 8601); unparseable → NaN |
| Filter Rows | `FilterRows` | `col: str`, `values: list[str]` | may reduce | rows not matching filter removed; no-op if values list is empty |
| Rename Columns | `RenameColumns` | `mapping: dict[str, str]` | preserved | column names changed per mapping; unmapped columns untouched |

---

### Stage 3: Load

**Output formats:**
- **CSV** — UTF-8, comma-delimited, `index=False`. Returns `BytesIO` (UI) or writes to path (CLI).
- **Excel** — OOXML `.xlsx`, openpyxl engine, single worksheet named "ETL Output", `index=False`. Returns `BytesIO` or writes to path.
- **SQLite SQL dump** — `CREATE TABLE` + `INSERT INTO` statements generated via `sqlite3.connect(":memory:")` → `df.to_sql()` → `iterdump()`. Returns UTF-8 `BytesIO`. Zero file I/O.
- **SQLite database** — writes a `.db` file to disk via `df.to_sql()` with `if_exists="replace"`.

**Encoding:** UTF-8 for all text formats.

**Row count audit:** `PipelineResult.rows_dropped_total = rows_extracted - rows_loaded` provides the net row reduction across all transform steps.

---

## Step Dependency Graph

The default 9-step pipeline applies steps in an order that satisfies semantic dependencies. Reordering steps in the custom pipeline builder changes output behavior:

```
NormalizeHeaders ──► All subsequent steps that reference column names by name
                     (DropNullRows, FillNulls, NormalizeText, CoerceNumeric,
                      CoerceDates, FilterRows, RenameColumns)

StripStrings ──────► Should precede type-coercion steps to ensure "$2,278,286 "
                     (with trailing space) parses correctly

DropDuplicates ────► Should precede DropNullRows: removes structural duplicates
                     before null-based row dropping changes row identity

DropNullRows ──────► Should precede FillNulls: removes unfixable rows before
                     filling remaining nulls

CoerceNumeric ─────► Should follow NormalizeHeaders (operates on snake_case name)
                     and StripStrings (ensures no surrounding whitespace in value)

CoerceDates ───────► Same as CoerceNumeric — order after header normalization
                     and whitespace stripping
```

**FilterRows and RenameColumns** are position-independent in most pipelines. FilterRows applied early reduces the data volume for subsequent steps; applied late it can reference columns created or renamed by earlier steps.

---

## Component Reference

| Module | Class / Function | Role |
|---|---|---|
| `src/extractor.py` | `extract_csv()`, `extract_sample()` | Stage 1 — source ingestion |
| `src/transformer.py` | `TransformStep`, `StepResult`, 10 step classes, `STEP_REGISTRY` | Stage 2 — all transformation logic |
| `src/loader.py` | `load_csv()`, `load_excel()`, `load_sqlite()`, `load_sqlite_sql()` | Stage 3 — output targets |
| `src/pipeline.py` | `run_pipeline()`, `default_steps()`, `PipelineResult` | Orchestration + audit trail |
| `app/main.py` | Streamlit app | UI layer — configuration, monitoring, download |
| `scripts/run_pipeline.py` | CLI `main()` | Batch automation entry point |

---

## Design Decisions

### Decision 1: All columns read as `str` in the Extract stage

Reading all CSV columns as `dtype=str` preserves values that pandas would otherwise auto-coerce. The value `"$2,278,286"` is kept as a string until `CoerceNumeric` handles it; `"01/15/2025"` is kept until `CoerceDates` applies the correct format. Allowing pandas to auto-detect types would silently transform these values — dates would be parsed using pandas' default format inference, which can be ambiguous on MM/DD vs DD/MM, and currency strings would become NaN. The explicit all-str read ensures the pipeline controls all type coercions, not pandas.

### Decision 2: Pure function immutability (`df.copy()` in every `apply()`)

Each `TransformStep.apply()` method begins with `df = df.copy()`. This makes every step a pure function — given the same input, it always produces the same output and never modifies the caller's DataFrame. The consequence is slightly higher memory usage (one copy per step), but the benefit is that steps are independently testable without setup/teardown, composable in any order without state leakage, and safe to reuse across pipeline runs. The test suite validates this directly: `TestNormalizeHeaders.test_does_not_mutate` and `TestStripStrings.test_does_not_mutate` verify that the original DataFrame is unchanged after `apply()`.

### Decision 3: `PipelineResult` as an immutable snapshot over mutable accumulator

`run_pipeline()` accumulates `StepResult` records in a list and assembles them into a `PipelineResult` only at the end of the run. The UI receives a single complete result object rather than a progressively-updating state. This enables `@st.cache_data` caching — the entire result is the cache value — and prevents partial-render states where the UI would show incomplete step counts or intermediate row counts.

### Decision 4: In-memory SQLite for SQL dump via `iterdump()`

`load_sqlite_sql()` creates a `sqlite3.connect(":memory:")` connection, loads the DataFrame into it, and calls `conn.iterdump()` to generate `CREATE TABLE + INSERT` SQL statements as strings. The result is a portable SQL text file that any SQLite client can execute. The alternative — writing a `.db` file to the server's temp directory — would require temp file cleanup, would hold a lock on Windows during the export, and would produce a binary format that is less portable. The in-memory approach avoids all file I/O: no disk write, no lock, no cleanup required.

### Decision 5: `STEP_REGISTRY` dictionary for UI-driven step selection

The `STEP_REGISTRY` dict maps display names (`"Normalize Headers"`) to step classes (`NormalizeHeaders`). The Streamlit sidebar multiselect lists the dict keys; when the user selects a step, the UI looks up the class in `STEP_REGISTRY` and instantiates it with defaults. This decouples step registration from the UI: adding a new step requires one `STEP_REGISTRY` entry, not any UI modification. It also allows the registry to be tested independently of the Streamlit layer.

---

## Known Limitations

- **CSV-only input:** The extractor reads only CSV files. Excel, JSON, Parquet, and database sources are not supported.
- **Default pipeline parameters are code-only:** The default step sequence is configurable via the UI (add/remove steps), but per-step parameters (which columns to coerce, which values to filter) use hardcoded defaults. Changing parameters requires editing `default_steps()` in `src/pipeline.py`.
- **`CoerceDates` uses `format="mixed"` with `dayfirst=False`:** Pandas treats ambiguous two-digit date fields (e.g., `01/02/2024`) as month-first (January 2nd, not February 1st). Datasets with day-first date conventions require changing the `dayfirst` parameter in `CoerceDates.apply()`.
- **`FilterRows` uses substring matching, not exact equality:** The filter uses `str.contains(regex_pattern, case=False)`. A filter value of `"act"` would match both `"Active"` and `"Enacted"`.
- **No output schema validation:** The pipeline does not verify that the cleaned DataFrame matches a target schema. Column presence and types after transformation are the caller's responsibility.

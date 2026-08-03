# Engineering Decisions — ETL Pipeline Builder

---

## ED-1: All CSV columns read as `str` dtype

**Decision:** `extract_csv()` reads every column as `dtype=str` by not specifying dtype and by passing no converters, then relying on downstream steps for type coercion.

**Alternative considered:** Let pandas infer dtypes on load (`pd.read_csv()` defaults).

**Why this was rejected:** Pandas dtype inference makes silent, irreversible decisions. A currency column `"$2,278,286"` becomes `NaN` (parse fails). A date column with two-digit years or mixed delimiters becomes either a string (if parsing fails) or a datetime with pandas' default format assumption (if parsing succeeds but guesses wrong). The pipeline cannot distinguish between a value that was always `NaN` and one that became `NaN` due to type inference. Reading as `str` preserves every value exactly as it appears in the source file and defers all coercion decisions to named, testable steps — `CoerceNumeric` and `CoerceDates` — that are explicit about their behavior on parse failure.

**Trade-off accepted:** All columns start as `object` dtype. Steps that operate on numeric or date types must coerce first. This adds one step per type transition but makes the transition visible in the run log.

---

## ED-2: Pure function contract for all `TransformStep.apply()` methods

**Decision:** Every `TransformStep.apply()` begins with `df = df.copy()` and returns a new DataFrame. The input is never modified.

**Alternative considered:** In-place mutation of the input DataFrame, which would avoid the memory cost of one copy per step.

**Why this was chosen:** In-place mutation creates hidden state dependencies between steps. If step 3 drops rows and step 4 reads `len(df)` expecting the original count, the result depends on execution order and is wrong in non-obvious ways. Pure functions eliminate this class of bug: each step produces a deterministic output given its input, regardless of what came before or after. This is not just a style preference — `TestNormalizeHeaders.test_does_not_mutate` and `TestStripStrings.test_does_not_mutate` exist specifically to enforce this contract so it cannot be accidentally broken.

**Trade-off accepted:** One DataFrame copy per step. For the sample dataset (90 rows × 10 columns), the overhead is negligible. At production scale, the copy cost would need to be profiled.

---

## ED-3: `PipelineResult` assembled as a complete snapshot, not a progressive state

**Decision:** `run_pipeline()` assembles a `PipelineResult` only after all steps have completed. The UI receives one complete object.

**Alternative considered:** Streaming results to the UI as each step finishes, updating displays incrementally.

**Why this was chosen:** Streamlit's `@st.cache_data` caches a function's return value keyed on its arguments. If the pipeline returns a partial result and then updates it, the cache mechanism breaks — the cached value would be stale. The complete-snapshot approach allows `cached_run(file_bytes)` in `app/main.py` to cache the entire pipeline result keyed on the raw file bytes. A re-render of the same input hits the cache instantly; a new file invalidates the cache and re-runs the pipeline. There is no partial-result state that could leave the UI showing an inconsistent step count or incorrect row totals.

**Trade-off accepted:** No progress indication during a long-running pipeline. This is acceptable for the current data sizes. A streaming approach would require a different UI architecture (e.g., `st.empty()` placeholders updated inside the pipeline loop) and would break caching.

---

## ED-4: In-memory SQLite for SQL dump generation

**Decision:** `load_sqlite_sql()` uses `sqlite3.connect(":memory:")`, loads the DataFrame into the in-memory database with `df.to_sql()`, and calls `conn.iterdump()` to produce `CREATE TABLE + INSERT` SQL statements as a string returned in a `BytesIO` buffer.

**Alternative considered:** Write a real `.db` file to a temp directory and read it back, or generate INSERT statements manually.

**Why in-memory was chosen:** Writing to disk requires cleanup. On Windows, an open SQLite file holds a file lock that cannot be released until the connection closes; if the connection is not properly closed, the lock persists and interferes with subsequent access. In-memory avoids the lock entirely. `iterdump()` produces standards-compliant SQL that any SQLite client can execute, making the export portable without distributing the binary `.db` format.

**Why not manual INSERT generation:** `iterdump()` correctly handles column naming, data types, and SQL escaping for the full range of pandas dtype-to-SQLite conversions. Manual generation would require re-implementing this mapping and would be a maintenance burden as column types evolve.

---

## ED-5: `STEP_REGISTRY` for decoupled UI-to-class mapping

**Decision:** A module-level `STEP_REGISTRY` dict maps string display names to step classes. The sidebar multiselect uses `STEP_REGISTRY.keys()` as options; selection triggers `STEP_REGISTRY[name]()` to instantiate the step.

**Alternative considered:** A series of `if name == "Normalize Headers"` conditionals in the UI layer.

**Why the registry was chosen:** The conditional chain couples the UI layer to every step class name and must be updated every time a step is added or renamed. The registry inverts this: adding a new step requires one dict entry in `src/transformer.py` with no UI changes. The registry is also independently testable — `TestStepRegistry` verifies that all registered names instantiate without error without involving the Streamlit layer. This is the same pattern as plugin registries in larger frameworks, applied at small scale.

---

## ED-6: `TransformStep` as an abstract dataclass, not a class hierarchy with `__init__`

**Decision:** `TransformStep` is a `@dataclass` with a `name` field and an abstract `apply()` method. Concrete steps are also dataclasses with their own fields (e.g., `columns: list[str]`). There is no `__init__` in the base class.

**Alternative considered:** A conventional class hierarchy with `__init__(self, name, **kwargs)`.

**Why dataclasses were chosen:** Dataclasses give each step a concise, declarative schema: `@dataclass class DropNullRows(TransformStep): columns: list[str] = field(default_factory=list)`. The field names are the configuration parameters; their types and defaults are self-documenting. `repr=True` (the default) makes `print(step)` produce a readable representation of the step's configuration, which appears in the run log `notes` field for error cases. A traditional `__init__` would produce the same functionality but with more boilerplate and no automatic repr.

---

*This document is a repository artifact and may be committed to the published repository.*

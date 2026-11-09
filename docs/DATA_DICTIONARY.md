# Data Dictionary — ETL Pipeline Builder

---

## Input Schema

Source: `data/sample/sample_raw.csv`

The sample dataset represents a synthetic government contracts register. Column names arrive with mixed casing and spaces (e.g., `"Contract ID"`, `"Agency Name"`). `NormalizeHeaders` converts them to snake_case as the first pipeline step.

| Original Column Name | snake_case Name | Raw Type | Description | Sample Raw Value |
|---|---|---|---|---|
| `Contract ID` | `contract_id` | str | Unique contract identifier assigned by the procurement office | `CTR-DEMO-2025-0001` |
| `Agency Name` | `agency_name` | str | Full name of the awarding federal agency | `Department of Defense` |
| `Vendor` | `vendor` | str | Prime contractor name; may have leading/trailing whitespace | `  Apex Federal Solutions  ` |
| `Category` | `category` | str | Procurement category | `IT Services` |
| `Contract Value` | `contract_value` | str (raw) | Total obligated contract value; formatted as currency string, comma-separated number, or plain integer | `$2,278,286` / `3,952,827` / `500000` |
| `Start Date` | `start_date` | str (raw) | Contract start date; mixed date formats in raw data | `2024-03-15` / `10/21/2024` / `01-23-2025` |
| `End Date` | `end_date` | str (raw) | Contract end date; same mixed-format issue as Start Date | `2025-09-30` / `12/31/2026` |
| `Status` | `status` | str | Execution status; inconsistent casing across records | `ACTIVE` / `Active` / `active` |
| `Award Year` | `award_year` | str | Calendar year contract was awarded | `2024` |
| `Notes` | `notes` | str | Free-text notes field; may be empty string, `"N/A"`, or `"TBD"` | `High priority` / `` / `N/A` |

**Row count:** 90 rows (80 unique records + ~10 intentional duplicate rows injected by `scripts/generate_sample_data.py`)

**Intentional data quality issues in sample data:**
- Mixed-case status values: `ACTIVE`, `Active`, `active` within the same column
- Currency-formatted contract values: `$2,278,286`, `3,952,827`, `500000`
- Mixed date formats: `%Y-%m-%d`, `%m/%d/%Y`, `%m-%d-%Y`, `%d/%m/%Y`
- Leading/trailing whitespace in vendor names: `"  Apex Federal Solutions  "`
- Empty string and `"N/A"` notes fields
- ~10 exact duplicate rows
- ~8% null values in `Agency Name`

---

## Output Schema

The following shows each column's state after the default 9-step pipeline completes.

| Column | Post-Transform Name | Output Type | Transformation Applied | Output Range / Format |
|---|---|---|---|---|
| `contract_id` | `contract_id` | str | Header normalized to snake_case; whitespace stripped | e.g., `CTR-DEMO-2025-0001` |
| `agency_name` | `agency_name` | str | Header normalized; rows with null/empty dropped | Non-empty string values only |
| `vendor` | `vendor` | str | Header normalized; whitespace stripped; title-cased | `Apex Federal Solutions` |
| `category` | `category` | str | Header normalized; whitespace stripped | `IT Services` |
| `contract_value` | `contract_value` | float64 | Header normalized; currency/comma-format stripped; coerced to float via `pd.to_numeric` | Numeric float or NaN for unparseable values |
| `start_date` | `start_date` | str | Header normalized; parsed to ISO 8601 via `pd.to_datetime(format="mixed")` + `.dt.strftime` | `YYYY-MM-DD` string or NaN |
| `end_date` | `end_date` | str | Same as `start_date` | `YYYY-MM-DD` string or NaN |
| `status` | `status` | str | Header normalized; whitespace stripped; title-cased | `Active` / `Completed` / `Pending` / `Cancelled` |
| `award_year` | `award_year` | str | Header normalized; whitespace stripped | `2024` / `2025` |
| `notes` | `notes` | str | Header normalized; NaN/empty filled with `"None"` | Non-null string |

**Expected output row count:** 90 raw rows → minus ~10 duplicates → minus ~7 null agency rows ≈ **73–76 rows** (varies by random seed in generate_sample_data.py).

---

## Transformation Catalog

### Step 1: NormalizeHeaders

| Before | After | Rule Applied |
|---|---|---|
| `Contract ID` | `contract_id` | strip → `re.sub(r"[\s\-]+", "_")` → `re.sub(r"[^\w]", "")` → `.lower()` |
| `Agency Name` | `agency_name` | same |
| `Contract Value` | `contract_value` | same |
| `Start Date` | `start_date` | same |
| `End Date` | `end_date` | same |
| `Award Year` | `award_year` | same |

*All 10 column names are snake_cased. Columns with no spaces or special characters are only lowercased.*

---

### Step 2: StripStrings

| Before | After | Rule Applied |
|---|---|---|
| `"  Apex Federal Solutions  "` | `"Apex Federal Solutions"` | `str.strip()` on all string cells |
| `"  See attached  "` | `"See attached"` | same |
| `NaN` | `NaN` | NaN values preserved (not converted to string) |

---

### Step 3: DropDuplicates

| Before | After |
|---|---|
| 90 rows (includes ~10 exact duplicates) | ~80 rows (exact duplicates removed) |

---

### Step 4: DropNullRows (columns=["agency_name"])

| Before | After |
|---|---|
| ~80 rows (some with empty agency_name) | ~73–76 rows (rows with null/empty agency_name dropped) |

---

### Step 5: FillNulls (values={"notes": "None"})

| Column | Before | After |
|---|---|---|
| `notes` | `""` / `NaN` / `"N/A"` | `""` and `NaN` → `"None"` (N/A values are strings, not null, so they remain) |

*Note: `"N/A"` is a string value, not null. `FillNulls` only replaces actual empty strings and NaN. `"N/A"` strings remain unless explicitly handled by an additional step.*

---

### Step 6–7: NormalizeText

| Column | Before | After | Case Mode |
|---|---|---|---|
| `status` | `"ACTIVE"` / `"active"` / `"Active"` | `"Active"` | title |
| `status` | `"COMPLETED"` | `"Completed"` | title |
| `vendor` | `"nexus systems llc"` | `"Nexus Systems Llc"` | title |

---

### Step 8: CoerceNumeric (columns=["contract_value"])

| Before | After | Rule |
|---|---|---|
| `"$2,278,286"` | `2278286.0` | `str.replace(r"[\$,]", "")` → `pd.to_numeric` |
| `"3,952,827"` | `3952827.0` | same |
| `"500000"` | `500000.0` | same |
| `""` | `NaN` | empty string → NaN |
| `"N/A"` | `NaN` | explicit NaN mapping in CoerceNumeric |

---

### Step 9: CoerceDates (columns=["start_date", "end_date"])

| Before | After | Rule |
|---|---|---|
| `"2024-03-15"` | `"2024-03-15"` | ISO 8601 preserved |
| `"10/21/2024"` | `"2024-10-21"` | `pd.to_datetime(format="mixed", dayfirst=False)` |
| `"01-23-2025"` | `"2025-01-23"` | same |
| unparseable | `NaN` | `errors="coerce"` |

**Ambiguity note:** `format="mixed"` with `dayfirst=False` treats ambiguous two-digit fields as month-first (US convention). Datasets with day-first date conventions require `dayfirst=True`.

---

## Export Schema

### CSV export (`etl_output.csv`)

Same 10 columns as the output schema above. UTF-8 encoding, comma-delimited, no index column. NaN values export as empty cells.

### Excel export (`etl_output.xlsx`)

Single worksheet named "ETL Output". Same 10 columns. Column headers in row 1; data begins in row 2. openpyxl engine (OOXML / ISO/IEC 29500).

### SQL dump (`etl_output.sql`)

Portable SQLite-compatible text: `BEGIN TRANSACTION;` → `CREATE TABLE "contracts"` with column definitions → `INSERT INTO "contracts" VALUES (...)` for each row → `COMMIT;`. Generated via `iterdump()` — compatible with any SQLite client.

### Audit log (`etl_audit_log.csv`)

| Column | Type | Description |
|---|---|---|
| `Step` | str | Display name of the transform step |
| `Rows In` | int | Row count entering this step |
| `Rows Out` | int | Row count leaving this step |
| `Rows Dropped` | int | `Rows In − Rows Out` |
| `Duration (ms)` | float | Wall-clock execution time in milliseconds |
| `Notes` | str | Error message if step raised an exception; empty otherwise |

---

## Data Source Note

`data/sample/sample_raw.csv` is a **synthetic** dataset generated by `scripts/generate_sample_data.py` using `random.seed(42)`. It is not exported from any live government system. The dataset represents the data quality characteristics common to government contract registers maintained in spreadsheets or agency tracking systems.

This tool does not connect to, import from, or depend on:
- FPDS-NG (Federal Procurement Data System — Next Generation)
- SAM.gov (System for Award Management)
- USASpending.gov
- Any agency ERP or financial system
- Any external API or web service

All data processed by this pipeline is provided by the user via file upload or the bundled sample CSV.

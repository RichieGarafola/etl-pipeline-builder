"""
ETL Pipeline Builder — CLI entry point.

Usage
-----
Run the default pipeline on a CSV file:

    python scripts/run_pipeline.py --input data/sample/sample_raw.csv --output results/cleaned.csv

With optional SQLite database and audit log:

    python scripts/run_pipeline.py \\
        --input  data/sample/sample_raw.csv \\
        --output results/cleaned.csv \\
        --sqlite results/etl_output.db \\
        --audit-log results/etl_audit_log.csv

Arguments
---------
--input      Path to the input CSV file (required).
--output     Path for the cleaned CSV output (required). Parent directories are
             created automatically.
--sqlite     Optional path for a SQLite database output (.db).
--audit-log  Optional path for the step-by-step audit log CSV
             (rows in/out, duration per step).
"""

import argparse
import sys
from pathlib import Path

# Resolve project root so imports work when the script is invoked from any cwd.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import run_pipeline, default_steps
from src.loader import load_csv, load_sqlite


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run_pipeline",
        description="ETL Pipeline Builder — run the default pipeline on a CSV file.",
    )
    parser.add_argument("--input",     required=True,  help="Path to input CSV file")
    parser.add_argument("--output",    required=True,  help="Path for cleaned CSV output")
    parser.add_argument("--sqlite",    default=None,   help="Optional: path to write SQLite database")
    parser.add_argument("--audit-log", default=None,   dest="audit_log",
                        help="Optional: path to write step-by-step audit log CSV")
    args = parser.parse_args()

    print(f"ETL Pipeline Builder")
    print(f"  Input:  {args.input}")
    print(f"  Output: {args.output}")
    print()

    result = run_pipeline(default_steps(), source_path=args.input)

    if not result.success:
        print(f"ERROR: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"  Rows extracted : {result.rows_extracted:,}")
    print(f"  Rows loaded    : {result.rows_loaded:,}")
    print(f"  Rows dropped   : {result.rows_dropped_total:,}")
    print(f"  Duration       : {result.total_duration_ms:.1f} ms")
    print()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    load_csv(result.output_df, path=output_path)
    print(f"  CSV saved      : {args.output}")

    if args.sqlite:
        sqlite_path = Path(args.sqlite)
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        load_sqlite(result.output_df, db_path=sqlite_path, table="etl_output")
        print(f"  SQLite saved   : {args.sqlite}")

    if args.audit_log:
        audit_path = Path(args.audit_log)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        result.summary_df().to_csv(str(audit_path), index=False)
        print(f"  Audit log saved: {args.audit_log}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()

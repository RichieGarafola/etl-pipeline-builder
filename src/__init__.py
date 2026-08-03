"""
ETL Pipeline Builder — public API.

Typical usage::

    from src import run_pipeline, default_steps
    result = run_pipeline(default_steps(), source_path="data/sample/sample_raw.csv")
"""

from .extractor import extract_csv, extract_sample
from .transformer import (
    StepResult,
    TransformStep,
    NormalizeHeaders,
    StripStrings,
    DropDuplicates,
    DropNullRows,
    FillNulls,
    NormalizeText,
    CoerceNumeric,
    CoerceDates,
    FilterRows,
    RenameColumns,
    STEP_REGISTRY,
)
from .loader import load_csv, load_sqlite, load_sqlite_sql, load_excel
from .pipeline import PipelineResult, run_pipeline, default_steps

__all__ = [
    # Extraction
    "extract_csv",
    "extract_sample",
    # Transform primitives
    "StepResult",
    "TransformStep",
    # Concrete transform steps
    "NormalizeHeaders",
    "StripStrings",
    "DropDuplicates",
    "DropNullRows",
    "FillNulls",
    "NormalizeText",
    "CoerceNumeric",
    "CoerceDates",
    "FilterRows",
    "RenameColumns",
    "STEP_REGISTRY",
    # Load targets
    "load_csv",
    "load_sqlite",
    "load_sqlite_sql",
    "load_excel",
    # Pipeline orchestration
    "PipelineResult",
    "run_pipeline",
    "default_steps",
]

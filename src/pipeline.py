"""
Pipeline orchestrator — runs Extract → Transform steps → Load and
produces a structured run log.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import pandas as pd

from src.extractor    import extract_csv, extract_sample
from src.transformer  import TransformStep, StepResult
from src.loader       import load_csv, load_sqlite_sql


@dataclass
class PipelineResult:
    source_path:      str
    rows_extracted:   int
    rows_loaded:      int
    step_log:         list[StepResult]
    output_df:        pd.DataFrame
    total_duration_ms:float
    error:            str | None = None

    @property
    def success(self) -> bool:
        return self.error is None

    @property
    def rows_dropped_total(self) -> int:
        return self.rows_extracted - self.rows_loaded

    def summary_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {
                "Step":          r.name,
                "Rows In":       r.rows_in,
                "Rows Out":      r.rows_out,
                "Rows Dropped":  r.rows_dropped,
                "Duration (ms)": r.duration_ms,
                "Notes":         r.notes,
            }
            for r in self.step_log
        ])


def run_pipeline(
    steps: list[TransformStep],
    source_path=None,
) -> PipelineResult:
    """
    Execute the full ETL pipeline.

    1. Extract source CSV (sample if source_path is None)
    2. Apply each TransformStep in order
    3. Return a PipelineResult with the output DataFrame and full run log

    The Load step is left to the caller (UI or script) so the pipeline
    stays pure and testable without side effects.
    """
    t_start = time.perf_counter()
    label   = str(source_path) if source_path else "sample_raw.csv"

    try:
        df = extract_csv(source_path) if source_path else extract_sample()
    except Exception as exc:
        return PipelineResult(
            source_path=label, rows_extracted=0, rows_loaded=0,
            step_log=[], output_df=pd.DataFrame(),
            total_duration_ms=0.0, error=str(exc),
        )

    rows_extracted = len(df)
    step_log: list[StepResult] = []

    for step in steps:
        try:
            df, result = step.run(df)
            step_log.append(result)
        except Exception as exc:
            step_log.append(StepResult(
                name=step.name, rows_in=len(df), rows_out=len(df),
                duration_ms=0.0, notes=f"ERROR: {exc}",
            ))

    total_ms = (time.perf_counter() - t_start) * 1000

    return PipelineResult(
        source_path=label,
        rows_extracted=rows_extracted,
        rows_loaded=len(df),
        step_log=step_log,
        output_df=df,
        total_duration_ms=round(total_ms, 2),
    )


# ── Default pipeline for the sample dataset ────────────────────────────────────

def default_steps() -> list[TransformStep]:
    """
    Pre-configured steps tuned for sample_raw.csv.
    The UI uses these as the starting configuration.
    """
    from src.transformer import (
        NormalizeHeaders, StripStrings, DropDuplicates, DropNullRows,
        NormalizeText, CoerceNumeric, CoerceDates, FillNulls,
    )
    return [
        NormalizeHeaders(),
        StripStrings(),
        DropDuplicates(),
        DropNullRows(columns=["agency_name"]),
        FillNulls(values={"notes": "None"}),
        NormalizeText(columns=["status"], case="title"),
        NormalizeText(columns=["vendor"], case="title"),
        CoerceNumeric(columns=["contract_value"]),
        CoerceDates(columns=["start_date", "end_date"]),
    ]

"""Tests for src/pipeline.py"""

import pandas as pd
import pytest

from src.pipeline import run_pipeline, PipelineResult, default_steps
from src.transformer import NormalizeHeaders, StripStrings, DropDuplicates


def minimal_steps():
    return [NormalizeHeaders(), StripStrings()]


# ── run_pipeline ───────────────────────────────────────────────────────────────

class TestRunPipeline:
    def test_returns_pipeline_result(self):
        result = run_pipeline(minimal_steps())
        assert isinstance(result, PipelineResult)

    def test_success_on_sample(self):
        result = run_pipeline(minimal_steps())
        assert result.success

    def test_rows_extracted_positive(self):
        result = run_pipeline(minimal_steps())
        assert result.rows_extracted > 0

    def test_rows_loaded_leq_extracted(self):
        result = run_pipeline(minimal_steps())
        assert result.rows_loaded <= result.rows_extracted

    def test_step_log_length_matches_steps(self):
        steps = minimal_steps()
        result = run_pipeline(steps)
        assert len(result.step_log) == len(steps)

    def test_output_df_is_dataframe(self):
        result = run_pipeline(minimal_steps())
        assert isinstance(result.output_df, pd.DataFrame)

    def test_output_not_empty(self):
        result = run_pipeline(minimal_steps())
        assert not result.output_df.empty

    def test_duration_positive(self):
        result = run_pipeline(minimal_steps())
        assert result.total_duration_ms >= 0

    def test_headers_normalized_after_pipeline(self):
        result = run_pipeline([NormalizeHeaders()])
        cols = result.output_df.columns.tolist()
        assert all(c == c.lower() for c in cols)
        assert all(" " not in c for c in cols)

    def test_duplicates_removed(self):
        result_with_dedup  = run_pipeline([NormalizeHeaders(), DropDuplicates()])
        result_no_dedup    = run_pipeline([NormalizeHeaders()])
        assert result_with_dedup.rows_loaded <= result_no_dedup.rows_loaded

    def test_empty_steps_returns_raw(self):
        result = run_pipeline([])
        assert result.rows_loaded == result.rows_extracted

    def test_error_on_bad_path(self):
        result = run_pipeline(minimal_steps(), source_path="/nonexistent/file.csv")
        assert not result.success
        assert result.error is not None


# ── PipelineResult helpers ─────────────────────────────────────────────────────

class TestPipelineResult:
    def setup_method(self):
        self.result = run_pipeline(default_steps())

    def test_rows_dropped_total(self):
        r = self.result
        assert r.rows_dropped_total == r.rows_extracted - r.rows_loaded

    def test_summary_df_returns_dataframe(self):
        assert isinstance(self.result.summary_df(), pd.DataFrame)

    def test_summary_df_has_expected_columns(self):
        df = self.result.summary_df()
        for col in ["Step", "Rows In", "Rows Out", "Rows Dropped", "Duration (ms)"]:
            assert col in df.columns

    def test_summary_df_row_count_matches_log(self):
        df = self.result.summary_df()
        assert len(df) == len(self.result.step_log)


# ── default_steps ──────────────────────────────────────────────────────────────

class TestDefaultSteps:
    def test_returns_list(self):
        assert isinstance(default_steps(), list)

    def test_steps_are_not_empty(self):
        assert len(default_steps()) > 0

    def test_pipeline_with_default_steps_succeeds(self):
        result = run_pipeline(default_steps())
        assert result.success

    def test_default_pipeline_normalizes_headers(self):
        result = run_pipeline(default_steps())
        cols = result.output_df.columns.tolist()
        assert all(c == c.lower() for c in cols)

    def test_default_pipeline_coerces_contract_value(self):
        result = run_pipeline(default_steps())
        if "contract_value" in result.output_df.columns:
            non_null = result.output_df["contract_value"].dropna()
            assert pd.api.types.is_numeric_dtype(non_null)

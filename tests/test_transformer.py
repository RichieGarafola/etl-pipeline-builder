"""Tests for src/transformer.py"""

import pandas as pd
import pytest

from src.transformer import (
    NormalizeHeaders, StripStrings, DropDuplicates, DropNullRows,
    FillNulls, NormalizeText, CoerceNumeric, CoerceDates,
    FilterRows, RenameColumns, TransformStep, StepResult,
)


def make_df(**overrides) -> pd.DataFrame:
    data = {
        "Contract ID":     ["W01-001", "W01-002", "W01-002", "W01-003"],
        "Agency Name":     ["DoD", "", "DHS", "VA"],
        "Vendor":          ["  Apex LLC  ", "nexus", "nexus", "SUMMIT group"],
        "Contract Value":  ["$1,200,000", "500000", "", "$3,400,000"],
        "Start Date":      ["2025-01-01", "01/15/2025", "2025-03-01", "2025-04-01"],
        "Status":          ["ACTIVE", "active", "Active", "completed"],
    }
    data.update(overrides)
    return pd.DataFrame(data)


# ── NormalizeHeaders ───────────────────────────────────────────────────────────

class TestNormalizeHeaders:
    def test_snake_case(self):
        df = NormalizeHeaders().apply(make_df())
        assert "contract_id"    in df.columns
        assert "agency_name"    in df.columns
        assert "contract_value" in df.columns

    def test_strips_spaces(self):
        df = pd.DataFrame(columns=["  Col A  ", "B"])
        result = NormalizeHeaders().apply(df)
        assert "col_a" in result.columns

    def test_does_not_mutate(self):
        raw = make_df()
        NormalizeHeaders().apply(raw)
        assert "Contract ID" in raw.columns

    def test_hyphen_to_underscore(self):
        df = pd.DataFrame(columns=["start-date"])
        result = NormalizeHeaders().apply(df)
        assert "start_date" in result.columns


# ── StripStrings ───────────────────────────────────────────────────────────────

class TestStripStrings:
    def test_strips_vendor_whitespace(self):
        df = NormalizeHeaders().apply(make_df())
        result = StripStrings().apply(df)
        assert result["vendor"].iloc[0] == "Apex LLC"

    def test_does_not_mutate(self):
        raw = make_df()
        raw_val = raw["Vendor"].iloc[0]
        StripStrings().apply(raw)
        assert raw["Vendor"].iloc[0] == raw_val


# ── DropDuplicates ─────────────────────────────────────────────────────────────

class TestDropDuplicates:
    def test_removes_exact_duplicates(self):
        df = pd.DataFrame({"A": ["x", "y", "y"], "B": ["1", "2", "2"]})
        result = DropDuplicates().apply(df)
        assert len(result) == 2

    def test_no_duplicates_unchanged(self):
        df = pd.DataFrame({"A": ["x", "y", "z"]})
        result = DropDuplicates().apply(df)
        assert len(result) == 3

    def test_subset_parameter(self):
        df = make_df()
        result = DropDuplicates(subset=["Contract ID"]).apply(df)
        assert len(result) == len(df["Contract ID"].unique())


# ── DropNullRows ───────────────────────────────────────────────────────────────

class TestDropNullRows:
    def test_drops_empty_string_rows(self):
        df = NormalizeHeaders().apply(make_df())
        result = DropNullRows(columns=["agency_name"]).apply(df)
        assert "" not in result["agency_name"].values

    def test_missing_column_is_safe(self):
        df = make_df()
        result = DropNullRows(columns=["nonexistent"]).apply(df)
        assert len(result) == len(df)

    def test_empty_columns_list_returns_all(self):
        df = make_df()
        result = DropNullRows(columns=[]).apply(df)
        assert len(result) == len(df)


# ── FillNulls ──────────────────────────────────────────────────────────────────

class TestFillNulls:
    def test_fills_empty_string(self):
        df = NormalizeHeaders().apply(make_df())
        result = FillNulls(values={"agency_name": "Unknown"}).apply(df)
        assert "Unknown" in result["agency_name"].values

    def test_missing_column_is_safe(self):
        df = make_df()
        result = FillNulls(values={"nonexistent": "X"}).apply(df)
        assert len(result) == len(df)


# ── NormalizeText ──────────────────────────────────────────────────────────────

class TestNormalizeText:
    def test_title_case(self):
        df = NormalizeHeaders().apply(make_df())
        result = NormalizeText(columns=["status"], case="title").apply(df)
        assert result["status"].iloc[0] == "Active"
        assert result["status"].iloc[3] == "Completed"

    def test_upper_case(self):
        df = NormalizeHeaders().apply(make_df())
        result = NormalizeText(columns=["status"], case="upper").apply(df)
        assert result["status"].iloc[3] == "COMPLETED"

    def test_lower_case(self):
        df = NormalizeHeaders().apply(make_df())
        result = NormalizeText(columns=["status"], case="lower").apply(df)
        assert result["status"].iloc[0] == "active"

    def test_missing_column_is_safe(self):
        df = make_df()
        result = NormalizeText(columns=["nonexistent"]).apply(df)
        assert len(result) == len(df)


# ── CoerceNumeric ──────────────────────────────────────────────────────────────

class TestCoerceNumeric:
    def test_parses_currency_string(self):
        df = NormalizeHeaders().apply(make_df())
        result = CoerceNumeric(columns=["contract_value"]).apply(df)
        assert result["contract_value"].iloc[0] == pytest.approx(1_200_000.0)

    def test_parses_plain_number(self):
        df = NormalizeHeaders().apply(make_df())
        result = CoerceNumeric(columns=["contract_value"]).apply(df)
        assert result["contract_value"].iloc[1] == pytest.approx(500_000.0)

    def test_empty_becomes_nan(self):
        df = NormalizeHeaders().apply(make_df())
        result = CoerceNumeric(columns=["contract_value"]).apply(df)
        assert pd.isna(result["contract_value"].iloc[2])

    def test_missing_column_is_safe(self):
        df = make_df()
        result = CoerceNumeric(columns=["nonexistent"]).apply(df)
        assert len(result) == len(df)


# ── CoerceDates ────────────────────────────────────────────────────────────────

class TestCoerceDates:
    def test_iso_date_preserved(self):
        df = NormalizeHeaders().apply(make_df())
        result = CoerceDates(columns=["start_date"]).apply(df)
        assert result["start_date"].iloc[0] == "2025-01-01"

    def test_slash_format_parsed(self):
        df = NormalizeHeaders().apply(make_df())
        result = CoerceDates(columns=["start_date"]).apply(df)
        # 01/15/2025 should become 2025-01-15
        assert result["start_date"].iloc[1] == "2025-01-15"

    def test_missing_column_is_safe(self):
        df = make_df()
        result = CoerceDates(columns=["nonexistent"]).apply(df)
        assert len(result) == len(df)


# ── FilterRows ─────────────────────────────────────────────────────────────────

class TestFilterRows:
    def test_filters_by_value(self):
        df = NormalizeHeaders().apply(make_df())
        df = NormalizeText(columns=["status"], case="title").apply(df)
        result = FilterRows(col="status", values=["Active"]).apply(df)
        assert all("active" in s.lower() for s in result["status"])

    def test_empty_values_returns_all(self):
        df = make_df()
        result = FilterRows(col="Status", values=[]).apply(df)
        assert len(result) == len(df)

    def test_missing_column_returns_all(self):
        df = make_df()
        result = FilterRows(col="nonexistent", values=["x"]).apply(df)
        assert len(result) == len(df)


# ── RenameColumns ──────────────────────────────────────────────────────────────

class TestRenameColumns:
    def test_renames_column(self):
        df = NormalizeHeaders().apply(make_df())
        result = RenameColumns(mapping={"contract_id": "id"}).apply(df)
        assert "id" in result.columns
        assert "contract_id" not in result.columns

    def test_missing_key_is_safe(self):
        df = make_df()
        result = RenameColumns(mapping={"nonexistent": "x"}).apply(df)
        assert len(result.columns) == len(df.columns)


# ── StepResult / run() ─────────────────────────────────────────────────────────

class TestStepRun:
    def test_run_returns_tuple(self):
        step = NormalizeHeaders()
        out, result = step.run(make_df())
        assert isinstance(out, pd.DataFrame)
        assert isinstance(result, StepResult)

    def test_rows_in_equals_input(self):
        step = NormalizeHeaders()
        _, result = step.run(make_df())
        assert result.rows_in == len(make_df())

    def test_duration_is_positive(self):
        step = NormalizeHeaders()
        _, result = step.run(make_df())
        assert result.duration_ms >= 0

    def test_rows_dropped_calculated(self):
        df = make_df()
        step = DropDuplicates()
        _, result = step.run(df)
        assert result.rows_dropped == result.rows_in - result.rows_out

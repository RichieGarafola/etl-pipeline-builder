"""Tests for src/extractor.py"""

import pandas as pd
import pytest

from src.extractor import extract_csv, extract_sample, SAMPLE_PATH


class TestExtractSample:
    def test_returns_dataframe(self):
        df = extract_sample()
        assert isinstance(df, pd.DataFrame)

    def test_not_empty(self):
        df = extract_sample()
        assert not df.empty

    def test_reads_string_dtype(self):
        df = extract_sample()
        for col in df.columns:
            # pandas 2.x may return StringDtype rather than object; both are string-compatible
            assert pd.api.types.is_string_dtype(df[col]), f"Column '{col}' is not string dtype"

    def test_has_expected_columns(self):
        df = extract_sample()
        expected = {
            "Contract ID", "Agency Name", "Vendor", "Category",
            "Contract Value", "Start Date", "End Date", "Status",
            "Award Year", "Notes",
        }
        assert expected.issubset(set(df.columns))


class TestExtractCsv:
    def test_reads_from_explicit_path(self):
        df = extract_csv(SAMPLE_PATH)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_raises_on_empty_file(self, tmp_path):
        empty_csv = tmp_path / "empty.csv"
        empty_csv.write_text("col_a,col_b\n")  # header only, zero data rows
        with pytest.raises(ValueError, match="empty"):
            extract_csv(str(empty_csv))

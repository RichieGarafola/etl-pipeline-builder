"""Tests for src/loader.py"""

from io import BytesIO

import pandas as pd
import pytest

from src.loader import load_csv, load_sqlite, load_sqlite_sql, load_excel


def make_df() -> pd.DataFrame:
    return pd.DataFrame({
        "id":    ["A001", "A002", "A003"],
        "value": [100.0, 200.0, 300.0],
        "label": ["alpha", "beta", "gamma"],
    })


class TestLoadCsv:
    def test_returns_bytesio(self):
        buf = load_csv(make_df())
        assert isinstance(buf, BytesIO)

    def test_content_is_valid_csv(self):
        buf = load_csv(make_df())
        df = pd.read_csv(buf)
        assert list(df.columns) == ["id", "value", "label"]
        assert len(df) == 3

    def test_writes_to_disk(self, tmp_path):
        path = tmp_path / "output.csv"
        load_csv(make_df(), path=path)
        assert path.exists()
        df = pd.read_csv(path)
        assert len(df) == 3


class TestLoadSqliteSql:
    def test_returns_bytesio(self):
        buf = load_sqlite_sql(make_df())
        assert isinstance(buf, BytesIO)

    def test_content_has_create_table(self):
        buf = load_sqlite_sql(make_df(), table="test_table")
        content = buf.read().decode("utf-8")
        assert "CREATE TABLE" in content
        assert "test_table" in content


class TestLoadExcel:
    def test_returns_bytesio(self):
        buf = load_excel(make_df())
        assert isinstance(buf, BytesIO)

    def test_content_is_readable_excel(self):
        buf = load_excel(make_df())
        df = pd.read_excel(buf, engine="openpyxl")
        assert list(df.columns) == ["id", "value", "label"]
        assert len(df) == 3

    def test_writes_to_disk(self, tmp_path):
        path = tmp_path / "output.xlsx"
        load_excel(make_df(), path=path)
        assert path.exists()
        df = pd.read_excel(path, engine="openpyxl")
        assert len(df) == 3

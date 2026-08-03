"""Load step — write the transformed DataFrame to CSV or SQLite."""

import sqlite3
from io import BytesIO
from pathlib import Path

import pandas as pd


def load_csv(df: pd.DataFrame, path=None) -> BytesIO | str:
    """
    Write to CSV.
    - If path is given, writes to disk and returns the path string.
    - Otherwise returns a BytesIO buffer (for Streamlit download).
    """
    if path is not None:
        df.to_csv(str(path), index=False)
        return str(path)
    buf = BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


def load_sqlite(df: pd.DataFrame, db_path: str | Path, table: str = "etl_output",
                if_exists: str = "replace") -> str:
    """Write to a SQLite table. Returns path string."""
    with sqlite3.connect(str(db_path)) as conn:
        df.to_sql(table, conn, if_exists=if_exists, index=False)
    return str(db_path)


def load_excel(df: pd.DataFrame, path=None, sheet_name: str = "ETL Output") -> BytesIO:
    """
    Write to Excel (.xlsx) via openpyxl.
    - If path is given, writes to disk and returns the path string.
    - Otherwise returns a BytesIO buffer (for Streamlit download).
    Requires openpyxl>=3.1.0 (listed in requirements.txt).
    """
    if path is not None:
        df.to_excel(str(path), index=False, sheet_name=sheet_name, engine="openpyxl")
        return str(path)
    buf = BytesIO()
    df.to_excel(buf, index=False, sheet_name=sheet_name, engine="openpyxl")
    buf.seek(0)
    return buf


def load_sqlite_sql(df: pd.DataFrame, table: str = "etl_output") -> BytesIO:
    """
    Export to a portable SQL text dump (CREATE TABLE + INSERT statements).
    Uses only in-memory SQLite + iterdump() — zero file I/O, no Windows locking.
    Returns a UTF-8 BytesIO suitable for st.download_button.
    """
    conn = sqlite3.connect(":memory:")
    df.to_sql(table, conn, if_exists="replace", index=False)
    sql_text = "\n".join(conn.iterdump())
    conn.close()
    buf = BytesIO(sql_text.encode("utf-8"))
    buf.seek(0)
    return buf

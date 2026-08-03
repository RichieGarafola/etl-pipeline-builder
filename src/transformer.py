"""
Composable transformation steps for the ETL pipeline.

Each step is a dataclass with:
  name  — display label used in the run log
  apply(df) -> pd.DataFrame  — pure function (returns a copy, never mutates)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


# ── Step result ────────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    name:        str
    rows_in:     int
    rows_out:    int
    duration_ms: float
    notes:       str = ""

    @property
    def rows_dropped(self) -> int:
        return self.rows_in - self.rows_out


# ── Base step ──────────────────────────────────────────────────────────────────

@dataclass
class TransformStep:
    name: str = "base"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:  # pragma: no cover
        return df.copy()

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, StepResult]:
        t0  = time.perf_counter()
        out = self.apply(df)
        ms  = (time.perf_counter() - t0) * 1000
        return out, StepResult(
            name=self.name,
            rows_in=len(df),
            rows_out=len(out),
            duration_ms=round(ms, 2),
        )


# ── Concrete steps ─────────────────────────────────────────────────────────────

@dataclass
class NormalizeHeaders(TransformStep):
    """Convert all column names to snake_case."""
    name: str = "Normalize Headers"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        new_cols = []
        for col in df.columns:
            c = col.strip()
            c = re.sub(r"[\s\-]+", "_", c)
            c = re.sub(r"[^\w]", "", c)
            c = c.lower()
            new_cols.append(c or f"col_{len(new_cols)}")
        df.columns = new_cols
        return df


@dataclass
class StripStrings(TransformStep):
    """Strip leading/trailing whitespace from all string cells."""
    name: str = "Strip Whitespace"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in df.columns:
            df[col] = df[col].apply(
                lambda v: str(v).strip() if pd.notna(v) and str(v).strip() != "nan" else v
            )
        return df


@dataclass
class DropDuplicates(TransformStep):
    """Remove exact duplicate rows."""
    name:   str       = "Drop Duplicates"
    subset: list[str] | None = None

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.drop_duplicates(subset=self.subset).reset_index(drop=True)


@dataclass
class DropNullRows(TransformStep):
    """Drop rows where ANY of the specified columns are null/empty."""
    name:    str       = "Drop Null Rows"
    columns: list[str] = field(default_factory=list)

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        cols = [c for c in self.columns if c in df.columns]
        if not cols:
            return df
        # Treat empty strings as null
        mask = df[cols].apply(lambda s: s.replace("", pd.NA).notna()).all(axis=1)
        return df[mask].reset_index(drop=True)


@dataclass
class FillNulls(TransformStep):
    """Fill empty/NaN cells with specified fill values per column."""
    name:   str        = "Fill Nulls"
    values: dict[str, Any] = field(default_factory=dict)

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col, val in self.values.items():
            if col in df.columns:
                df[col] = df[col].replace("", pd.NA).fillna(val)
        return df


@dataclass
class NormalizeText(TransformStep):
    """Normalize string values in specified columns (strip + title/upper/lower)."""
    name:    str       = "Normalize Text"
    columns: list[str] = field(default_factory=list)
    case:    str       = "title"   # "title" | "upper" | "lower"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        fn = {"title": str.title, "upper": str.upper, "lower": str.lower}.get(self.case, str.strip)
        for col in self.columns:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda v: fn(str(v).strip()) if pd.notna(v) and str(v).strip() not in ("", "nan") else v
                )
        return df


@dataclass
class CoerceNumeric(TransformStep):
    """
    Parse currency/comma-formatted strings to float.
    Non-parseable values become NaN.
    """
    name:    str       = "Coerce Numeric"
    columns: list[str] = field(default_factory=list)

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in self.columns:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(r"[\$,]", "", regex=True)
                    .str.strip()
                    .replace({"": float("nan"), "nan": float("nan"), "N/A": float("nan")})
                    .pipe(pd.to_numeric, errors="coerce")
                )
        return df


@dataclass
class CoerceDates(TransformStep):
    """
    Parse date strings (multiple formats) to a standardised YYYY-MM-DD string.
    Unparseable values become NaN.
    """
    name:    str       = "Coerce Dates"
    columns: list[str] = field(default_factory=list)

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in self.columns:
            if col in df.columns:
                parsed = pd.to_datetime(df[col], errors="coerce", format="mixed", dayfirst=False)
                df[col] = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), other=float("nan"))
        return df


@dataclass
class FilterRows(TransformStep):
    """
    Keep rows where column `col` contains (case-insensitive) one of `values`.
    If values is empty, all rows are kept.
    """
    name:   str       = "Filter Rows"
    col:    str       = ""
    values: list[str] = field(default_factory=list)

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.col or not self.values or self.col not in df.columns:
            return df.copy()
        pat = "|".join(re.escape(v) for v in self.values)
        mask = df[self.col].astype(str).str.contains(pat, case=False, na=False)
        return df[mask].reset_index(drop=True)


@dataclass
class RenameColumns(TransformStep):
    """Rename specific columns."""
    name:    str        = "Rename Columns"
    mapping: dict[str, str] = field(default_factory=dict)

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.rename(columns={k: v for k, v in self.mapping.items() if k in df.columns})


# ── Registry (for UI step selection) ──────────────────────────────────────────

STEP_REGISTRY: dict[str, type[TransformStep]] = {
    "Normalize Headers": NormalizeHeaders,
    "Strip Whitespace":  StripStrings,
    "Drop Duplicates":   DropDuplicates,
    "Drop Null Rows":    DropNullRows,
    "Fill Nulls":        FillNulls,
    "Normalize Text":    NormalizeText,
    "Coerce Numeric":    CoerceNumeric,
    "Coerce Dates":      CoerceDates,
    "Filter Rows":       FilterRows,
    "Rename Columns":    RenameColumns,
}

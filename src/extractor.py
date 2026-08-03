"""Extract step — load source data into a DataFrame."""

from pathlib import Path
from io import BytesIO

import pandas as pd

SAMPLE_PATH = Path(__file__).parent.parent / "data" / "sample" / "sample_raw.csv"


def extract_csv(path=None, encoding: str = "utf-8") -> pd.DataFrame:
    """Load a CSV file or file-like object and return a raw DataFrame."""
    src = path or SAMPLE_PATH
    df = pd.read_csv(src, encoding=encoding, dtype=str)   # read all as str; types coerced later
    df.columns = df.columns.str.strip()                   # strip header whitespace only
    if df.empty:
        raise ValueError("Source CSV is empty.")
    return df


def extract_sample() -> pd.DataFrame:
    return extract_csv(SAMPLE_PATH)

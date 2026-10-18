"""CSV validation and loading. Raises CSVError with a user-friendly message."""
import csv
import io
import re
import warnings

import pandas as pd

from ..config import Settings


class CSVError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


DATE_PATTERN = re.compile(r"^\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})")


def decode_bytes(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def detect_delimiter(text: str) -> str:
    sample = text[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def unique_column_names(raw_names: list[str]) -> tuple[list[str], list[str]]:
    """Strip names, fill blanks and de-duplicate. Returns (names, warnings)."""
    names: list[str] = []
    seen: set[str] = set()
    notes: list[str] = []
    for i, raw in enumerate(raw_names, start=1):
        name = (raw or "").strip() or f"column_{i}"
        if not (raw or "").strip():
            notes.append(f"Unnamed column {i} was renamed to '{name}'.")
        base, n = name, 1
        while name.lower() in seen:
            n += 1
            name = f"{base}_{n}"
        if name != base:
            notes.append(f"Duplicate column name '{base}' was renamed to '{name}'.")
        seen.add(name.lower())
        names.append(name)
    return names, notes


def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Convert object columns that are really numbers / booleans / dates."""
    for col in df.columns:
        s = df[col]
        if s.dtype != object:
            continue
        non_null = s.dropna().astype(str).str.strip()
        non_null = non_null[non_null != ""]
        if non_null.empty:
            continue
        cleaned = non_null.str.replace(",", "", regex=False).str.rstrip("%")
        numeric = pd.to_numeric(cleaned, errors="coerce")
        if numeric.notna().mean() >= 0.95:
            df[col] = pd.to_numeric(s.astype(str).str.strip().str.replace(",", "", regex=False).str.rstrip("%"), errors="coerce")
            continue
        lowered = non_null.str.lower()
        if lowered.isin(["true", "false"]).all():
            df[col] = s.astype(str).str.strip().str.lower().map({"true": True, "false": False})
            continue
        if non_null.head(50).map(lambda v: bool(DATE_PATTERN.match(v))).mean() >= 0.9:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                parsed = pd.to_datetime(s, errors="coerce")
            if parsed.notna().sum() / max(len(non_null), 1) >= 0.9:
                df[col] = parsed
                continue
        df[col] = s.astype(str).str.strip().where(s.notna(), None)
    return df


def load_csv(raw: bytes, filename: str, settings: Settings) -> tuple[pd.DataFrame, list[str]]:
    if not filename.lower().endswith(".csv"):
        raise CSVError("Only .csv files are supported. Please upload a file ending in .csv.", 415)
    if not raw or not raw.strip():
        raise CSVError("The uploaded file is empty.")
    if len(raw) > settings.max_file_size_bytes:
        raise CSVError(
            f"The file is {len(raw) / 1024 / 1024:.1f} MB which exceeds the {settings.max_file_size_mb} MB limit.",
            413,
        )
    if b"\x00" in raw[:4096] and not raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise CSVError("This does not look like a text CSV file (binary content detected).")

    text = decode_bytes(raw)
    delimiter = detect_delimiter(text)
    try:
        header = next(csv.reader(io.StringIO(text), delimiter=delimiter))
    except (StopIteration, csv.Error):
        raise CSVError("Could not read a header row from the CSV.")
    names, notes = unique_column_names(header)

    try:
        df = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            header=0,
            names=names,
            skipinitialspace=True,
            on_bad_lines="error",
            engine="python" if len(delimiter) > 1 else "c",
        )
    except pd.errors.EmptyDataError:
        raise CSVError("The CSV file contains no data.")
    except (pd.errors.ParserError, ValueError) as exc:
        raise CSVError(f"The CSV is malformed and could not be parsed: {str(exc)[:200]}")

    df = df.dropna(how="all")
    if df.empty or len(df.columns) == 0:
        raise CSVError("The CSV has a header but no data rows.")
    if len(df) > settings.max_rows:
        raise CSVError(
            f"The dataset has {len(df):,} rows which exceeds the limit of {settings.max_rows:,} rows. "
            "Please upload a smaller file (rows are never silently truncated)."
        )
    df = coerce_types(df.reset_index(drop=True))
    return df, notes

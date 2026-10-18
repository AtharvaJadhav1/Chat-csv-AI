"""Dataset profiling: schema detection + per-column statistics."""
import pandas as pd
from pandas.api import types as ptypes

from ..schemas.api import ColumnKind, ColumnProfile, DatasetProfile, NumericStats, ValueCount
from ..utils.json_utils import to_py


def column_kind(s: pd.Series) -> ColumnKind:
    if ptypes.is_bool_dtype(s):
        return "boolean"
    if ptypes.is_numeric_dtype(s):
        return "numeric"
    if ptypes.is_datetime64_any_dtype(s):
        return "datetime"
    non_null = s.dropna()
    if len(non_null) and non_null.map(lambda v: isinstance(v, bool)).all():
        return "boolean"
    return "categorical"


def looks_like_identifier(name: str, s: pd.Series, kind: ColumnKind) -> bool:
    non_null = s.dropna()
    if non_null.empty or non_null.nunique() != len(non_null) or len(non_null) < 5:
        return False
    if kind == "numeric":
        return bool(
            ptypes.is_integer_dtype(s) or (non_null % 1 == 0).all()
        ) and ("id" in name.lower().replace("_", " ").split() or name.lower().endswith("id"))
    return False


def profile_column(name: str, s: pd.Series, total_rows: int) -> ColumnProfile:
    kind = column_kind(s)
    missing = int(s.isna().sum())
    unique = int(s.nunique(dropna=True))
    profile = ColumnProfile(
        name=name,
        kind=kind,
        dtype=str(s.dtype),
        missing=missing,
        missing_pct=round(100 * missing / total_rows, 2) if total_rows else 0.0,
        unique=unique,
        is_identifier=looks_like_identifier(name, s, kind),
    )
    non_null = s.dropna()
    if kind == "numeric" and not non_null.empty:
        profile.stats = NumericStats(
            mean=to_py(non_null.mean()),
            median=to_py(non_null.median()),
            min=to_py(non_null.min()),
            max=to_py(non_null.max()),
            std=to_py(non_null.std()) if len(non_null) > 1 else None,
        )
    elif kind == "datetime" and not non_null.empty:
        profile.min_value = non_null.min().isoformat()
        profile.max_value = non_null.max().isoformat()
    if kind in ("categorical", "boolean"):
        counts = non_null.astype(str).value_counts().head(8)
        profile.top_values = [ValueCount(value=str(k), count=int(v)) for k, v in counts.items()]
    profile.sample_values = [to_py(v) for v in non_null.head(3).tolist()]
    return profile


def profile_dataframe(df: pd.DataFrame, filename: str) -> DatasetProfile:
    cols = [profile_column(c, df[c], len(df)) for c in df.columns]

    def names(kind: str) -> list[str]:
        return [c.name for c in cols if c.kind == kind]

    return DatasetProfile(
        filename=filename,
        rows=len(df),
        columns=len(df.columns),
        missing_total=int(df.isna().sum().sum()),
        duplicate_rows=int(df.duplicated().sum()),
        numeric_columns=names("numeric"),
        categorical_columns=names("categorical"),
        datetime_columns=names("datetime"),
        boolean_columns=names("boolean"),
        column_profiles=cols,
    )

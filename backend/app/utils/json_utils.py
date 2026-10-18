import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


def to_py(value: Any) -> Any:
    """Convert numpy/pandas scalars into JSON-safe Python values (NaN/inf -> None)."""
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [to_py(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_py(v) for k, v in value.items()}
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value

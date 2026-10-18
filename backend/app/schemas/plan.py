"""Structured analysis plan produced by the LLM (or the rule-based planner).

The plan is DATA, never code: every field is validated against an allowlist before
the executor turns it into pandas operations.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Intent = Literal[
    "row_count",
    "column_count",
    "list_columns",
    "aggregation",
    "groupby_aggregation",
    "filter",
    "top_n",
    "bottom_n",
    "unique_values",
    "value_counts",
    "missing_values",
    "correlation",
    "distribution",
    "percentage",
    "describe",
    "unsupported",
    "clarification",
]
Operation = Literal["mean", "median", "min", "max", "sum", "count", "nunique", "std"]
Operator = Literal["==", "!=", ">", ">=", "<", "<=", "contains", "in", "not_in", "is_null", "not_null"]
ChartType = Literal["bar", "line", "pie", "histogram", "scatter", "area"]
DateGrain = Literal["year", "month", "day", "weekday"]

MAX_LIMIT = 1000

PLAN_FIELDS = {
    "intent", "operation", "column", "target_column", "group_by", "group_by_2", "date_grain", "conditions",
    "columns", "sort_by", "order", "limit", "x_column", "y_column", "bins", "chart", "message",
    "explanation",
}


class Condition(BaseModel):
    column: str
    operator: Operator
    value: Any = None

    @field_validator("value")
    @classmethod
    def value_must_be_scalar_or_list(cls, v: Any) -> Any:
        scalar = (str, int, float, bool, type(None))
        if isinstance(v, scalar):
            return v
        if isinstance(v, list) and all(isinstance(i, scalar) for i in v) and len(v) <= 200:
            return v
        raise ValueError("condition value must be a scalar or a list of scalars")


class ChartRequest(BaseModel):
    required: bool = False
    type: Optional[ChartType] = None
    x: Optional[str] = None
    y: Optional[str] = None


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: Intent
    operation: Optional[Operation] = None
    column: Optional[str] = None
    target_column: Optional[str] = None
    group_by: Optional[str] = None
    group_by_2: Optional[str] = None
    date_grain: Optional[DateGrain] = None
    conditions: list[Condition] = Field(default_factory=list, max_length=10)
    columns: list[str] = Field(default_factory=list, max_length=50)
    sort_by: Optional[str] = None
    order: Optional[Literal["asc", "desc"]] = None
    limit: Optional[int] = Field(default=None, ge=1, le=MAX_LIMIT)
    x_column: Optional[str] = None
    y_column: Optional[str] = None
    bins: Optional[int] = Field(default=None, ge=2, le=100)
    chart: Optional[ChartRequest] = None
    message: Optional[str] = Field(default=None, max_length=1000)
    explanation: Optional[str] = Field(default=None, max_length=1000)

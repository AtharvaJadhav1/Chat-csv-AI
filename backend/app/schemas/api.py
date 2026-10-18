from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ColumnKind = Literal["numeric", "categorical", "datetime", "boolean"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NumericStats(BaseModel):
    mean: Optional[float] = None
    median: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    std: Optional[float] = None


class ValueCount(BaseModel):
    value: Any
    count: int


class ColumnProfile(BaseModel):
    name: str
    kind: ColumnKind
    dtype: str
    missing: int
    missing_pct: float
    unique: int
    is_identifier: bool = False
    stats: Optional[NumericStats] = None
    top_values: list[ValueCount] = Field(default_factory=list)
    sample_values: list[Any] = Field(default_factory=list)
    min_value: Optional[str] = None
    max_value: Optional[str] = None


class DatasetProfile(BaseModel):
    filename: str
    rows: int
    columns: int
    missing_total: int
    duplicate_rows: int
    numeric_columns: list[str]
    categorical_columns: list[str]
    datetime_columns: list[str]
    boolean_columns: list[str]
    column_profiles: list[ColumnProfile]


class PreviewResponse(BaseModel):
    columns: list[str]
    kinds: dict[str, ColumnKind]
    rows: list[list[Any]]
    page: int
    page_size: int
    total_rows: int
    total_pages: int


class UploadResponse(BaseModel):
    dataset_id: str
    profile: DatasetProfile
    preview: PreviewResponse
    warnings: list[str] = Field(default_factory=list)


class TableData(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    total_rows: int
    truncated: bool = False


class ChartSpec(BaseModel):
    type: Literal["bar", "line", "pie", "histogram", "scatter", "area"]
    title: str
    xAxis: str
    yAxis: str
    data: list[dict[str, Any]]


class StatCard(BaseModel):
    label: str
    value: str


class AnalysisInfo(BaseModel):
    intent: str
    operation: Optional[str] = None
    column: Optional[str] = None
    explanation: str = ""
    plan: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    dataset_id: str
    question: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    status: Literal["ok", "unsupported", "clarification", "error"] = "ok"
    answer: str
    analysis: Optional[AnalysisInfo] = None
    stat: Optional[StatCard] = None
    table: Optional[TableData] = None
    chart: Optional[ChartSpec] = None
    planner: str = ""
    timestamp: datetime = Field(default_factory=utcnow)


class Insight(BaseModel):
    category: str
    title: str
    detail: str


class InsightsResponse(BaseModel):
    insights: list[Insight]
    generated_at: datetime = Field(default_factory=utcnow)


class HistoryItem(BaseModel):
    question: str
    answer: str
    intent: Optional[str] = None
    timestamp: datetime

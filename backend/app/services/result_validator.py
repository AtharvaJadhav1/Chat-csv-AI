"""Step 6 of the pipeline: sanity-check an execution result before it leaves the backend."""
import math

from ..security.plan_validator import PlanError
from .executor import MAX_TABLE_ROWS, ExecResult

MAX_CHART_ROWS = 1000


def _finite(value) -> bool:
    return not (isinstance(value, float) and (math.isnan(value) or math.isinf(value)))


def validate_result(result: ExecResult) -> ExecResult:
    if not result.answer or not result.answer.strip():
        raise PlanError("The analysis produced an empty result.")

    table = result.table
    if table is not None:
        if not table.columns or any(len(row) != len(table.columns) for row in table.rows):
            raise PlanError("The analysis produced a malformed table.")
        if len(table.rows) > MAX_TABLE_ROWS:
            raise PlanError("The analysis produced a table that is too large to display.")
        if not table.rows:
            result.table = None

    chart = result.chart
    if chart is not None:
        if not chart.data or len(chart.data) > MAX_CHART_ROWS:
            result.chart = None
        elif any(not _finite(v) for row in chart.data for v in row.values()):
            chart.data = [r for r in chart.data if all(_finite(v) and v is not None for v in r.values())]
            if not chart.data:
                result.chart = None
    return result

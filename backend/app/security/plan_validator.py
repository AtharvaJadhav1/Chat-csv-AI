"""Validates an AnalysisPlan against the real dataset schema.

Resolves column names, checks data types and coerces condition values. Nothing here
touches pandas execution; it only decides whether a plan is allowed to run.
"""
import difflib
import re
from typing import Any

import pandas as pd

from ..schemas.api import DatasetProfile
from ..schemas.plan import AnalysisPlan, ChartRequest, Condition
from ..utils.formatting import bullet_list


class PlanError(Exception):
    """A plan that cannot be executed. `status` maps to the chat response status."""

    def __init__(self, message: str, status: str = "error"):
        super().__init__(message)
        self.message = message
        self.status = status


NUMERIC_OPS = {"mean", "median", "sum", "std"}
ORDERING_OPERATORS = {">", ">=", "<", "<="}


def _norm(name: str) -> str:
    return re.sub(r"[\s_\-]+", "", name.strip().lower())


def _singular(name: str) -> str:
    return name[:-1] if name.endswith("s") and len(name) > 3 else name


class SchemaResolver:
    def __init__(self, profile: DatasetProfile):
        self.profile = profile
        self.kinds = {c.name: c.kind for c in profile.column_profiles}
        self.names = list(self.kinds)

    def find(self, ref: str) -> str | None:
        ref = ref.strip()
        if ref in self.kinds:
            return ref
        target = _norm(ref)
        for name in self.names:
            if _norm(name) == target:
                return name
        for name in self.names:
            if _singular(_norm(name)) == _singular(target):
                return name
        return None

    def available(self, kind: str | None) -> list[str]:
        if kind is None:
            return self.names
        return [n for n, k in self.kinds.items() if k == kind]

    def resolve(self, ref: str | None, kind: str | None = None) -> str | None:
        """Resolve a column reference; `kind` only controls which columns are suggested on failure."""
        if ref is None or not str(ref).strip():
            return None
        found = self.find(str(ref))
        if found:
            return found
        label = "numeric columns" if kind == "numeric" else "columns"
        lines = [f"I couldn't find a '{ref}' column in your dataset."]
        close = difflib.get_close_matches(str(ref), self.names, n=1, cutoff=0.6)
        if close:
            lines.append(f"Did you mean '{close[0]}'?")
        pool = self.available(kind) or self.names
        lines.append(f"\nAvailable {label}:\n{bullet_list(pool)}")
        raise PlanError("\n".join(lines))

    def require_kind(self, col: str, allowed: set[str], action: str) -> None:
        kind = self.kinds[col]
        if kind in allowed:
            return
        want = " or ".join(sorted(allowed))
        pool = [n for n, k in self.kinds.items() if k in allowed]
        hint = f"\n\nAvailable {want} columns:\n{bullet_list(pool)}" if pool else ""
        raise PlanError(f"I can't {action} because '{col}' is a {kind} column (a {want} column is needed).{hint}")


def _to_number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean")
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).strip().replace(",", "").replace("$", "").rstrip("%"))


def _coerce_value(value: Any, kind: str, column: str) -> Any:
    try:
        if kind == "numeric":
            return _to_number(value)
        if kind == "datetime":
            return pd.Timestamp(str(value)).isoformat()
        if kind == "boolean":
            text = str(value).strip().lower()
            if text in ("true", "yes", "1"):
                return True
            if text in ("false", "no", "0"):
                return False
            raise ValueError("boolean")
        return str(value).strip()
    except (ValueError, TypeError):
        raise PlanError(f"I can't compare the {kind} column '{column}' with the value '{value}'.")


def _validate_conditions(resolver: SchemaResolver, conditions: list[Condition]) -> list[Condition]:
    out: list[Condition] = []
    for cond in conditions:
        col = resolver.resolve(cond.column)
        kind = resolver.kinds[col]
        if cond.operator in ORDERING_OPERATORS and kind not in ("numeric", "datetime"):
            raise PlanError(f"The operator '{cond.operator}' only works on numeric or date columns, but '{col}' is {kind}.")
        if cond.operator == "contains" and kind != "categorical":
            raise PlanError(f"'contains' only works on text columns, but '{col}' is {kind}.")
        value = cond.value
        if cond.operator in ("is_null", "not_null"):
            value = None
        elif cond.operator in ("in", "not_in"):
            raw = value if isinstance(value, list) else [value]
            value = [_coerce_value(v, kind, col) for v in raw]
        else:
            if value is None or isinstance(value, list):
                raise PlanError(f"The filter on '{col}' needs a single value.")
            value = _coerce_value(value, kind, col)
        out.append(Condition(column=col, operator=cond.operator, value=value))
    return out


def _validate_chart(resolver: SchemaResolver, chart: ChartRequest | None) -> ChartRequest | None:
    if chart is None:
        return None
    # x/y may be result-column names (e.g. "average_marks"), so they are not hard errors.
    return chart


def validate_plan(plan: AnalysisPlan, profile: DatasetProfile) -> AnalysisPlan:
    """Return a copy of the plan with resolved column names, or raise PlanError."""
    if plan.intent == "unsupported":
        raise PlanError(
            plan.message or "This question cannot be answered from the uploaded dataset.", status="unsupported"
        )
    if plan.intent == "clarification":
        raise PlanError(
            plan.message or "Could you clarify your question? Mention the column or metric you care about.",
            status="clarification",
        )

    r = SchemaResolver(profile)
    upd: dict[str, Any] = {}
    intent, op = plan.intent, plan.operation

    upd["conditions"] = _validate_conditions(r, plan.conditions)
    upd["columns"] = [r.resolve(c) for c in plan.columns]
    upd["sort_by"] = r.resolve(plan.sort_by)
    upd["chart"] = _validate_chart(r, plan.chart)

    if intent == "aggregation":
        if op is None:
            raise PlanError("Which calculation should I perform (average, sum, count, min, max...)?", "clarification")
        col = r.resolve(plan.column or plan.target_column, "numeric" if op in NUMERIC_OPS else None)
        if col is None and op not in ("count",):
            raise PlanError("Which column should I calculate that for?", "clarification")
        if col is not None:
            if op in NUMERIC_OPS:
                r.require_kind(col, {"numeric"}, f"calculate the {op} of '{col}'")
            elif op in ("min", "max"):
                r.require_kind(col, {"numeric", "datetime"}, f"find the {op} of '{col}'")
        upd["column"] = col

    elif intent == "groupby_aggregation":
        group = r.resolve(plan.group_by or plan.column, None)
        if group is None:
            raise PlanError("Which column should I group by?", "clarification")
        target_ref = plan.target_column or (plan.column if plan.group_by else None)
        target = r.resolve(target_ref, "numeric" if (op or "mean") in NUMERIC_OPS else None)
        op = op or ("mean" if target else "count")
        if target is None and op != "count":
            raise PlanError(f"Which column should I calculate the {op} of?", "clarification")
        if target is not None:
            if op in NUMERIC_OPS:
                r.require_kind(target, {"numeric"}, f"calculate the {op} of '{target}'")
            elif op in ("min", "max"):
                r.require_kind(target, {"numeric", "datetime"}, f"find the {op} of '{target}'")
        grain = plan.date_grain
        if r.kinds[group] == "datetime":
            grain = grain or "month"
        else:
            grain = None
        group2 = r.resolve(plan.group_by_2, None)
        if group2 == group:
            group2 = None
        if group2 and r.kinds[group2] == "datetime":
            raise PlanError("A second grouping column can't be a date column; group by dates on their own.")
        upd.update(group_by=group, group_by_2=group2, target_column=target, operation=op, date_grain=grain)

    elif intent in ("top_n", "bottom_n"):
        col = r.resolve(plan.column or plan.sort_by or plan.target_column, "numeric")
        if col is None:
            raise PlanError("Which column should I rank by?", "clarification")
        r.require_kind(col, {"numeric", "datetime"}, f"rank rows by '{col}'")
        upd["column"] = col

    elif intent in ("unique_values", "value_counts"):
        col = r.resolve(plan.column or plan.group_by or plan.target_column)
        if col is None:
            raise PlanError("Which column should I look at?", "clarification")
        upd["column"] = col

    elif intent == "missing_values":
        upd["column"] = r.resolve(plan.column)

    elif intent == "correlation":
        x = r.resolve(plan.x_column or plan.column, "numeric")
        y = r.resolve(plan.y_column or plan.target_column, "numeric")
        if (x is None) != (y is None):
            raise PlanError("A correlation needs two numeric columns. Which two should I compare?", "clarification")
        for c in (x, y):
            if c:
                r.require_kind(c, {"numeric"}, f"correlate '{c}'")
        if x and x == y:
            raise PlanError("A correlation needs two different columns.", "clarification")
        upd.update(x_column=x, y_column=y)

    elif intent == "distribution":
        col = r.resolve(plan.column or plan.target_column, "numeric")
        if col is None:
            raise PlanError("Which column's distribution should I show?", "clarification")
        if r.kinds[col] in ("categorical", "boolean"):
            upd["intent"] = "value_counts"
        else:
            r.require_kind(col, {"numeric"}, f"plot the distribution of '{col}'")
        upd["column"] = col

    elif intent == "percentage":
        if not upd["conditions"]:
            raise PlanError("Which group or condition should I calculate the percentage for?", "clarification")

    elif intent == "describe":
        upd["column"] = r.resolve(plan.column or plan.target_column)

    elif intent == "filter":
        pass

    return plan.model_copy(update=upd)

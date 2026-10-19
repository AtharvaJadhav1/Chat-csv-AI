"""Safe analysis executor.

Turns a *validated* AnalysisPlan into allowlisted pandas operations. There is no
eval/exec and no dynamic code: each intent maps to a fixed function below.
"""
import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from ..schemas.api import ChartSpec, DatasetProfile, StatCard, TableData
from ..schemas.plan import AnalysisPlan, Condition
from ..security.plan_validator import PlanError
from ..utils.formatting import fmt_num
from ..utils.json_utils import to_py

MAX_TABLE_ROWS = 200
MAX_CHART_POINTS = 500
MAX_CHART_GROUPS = 50

OP_LABEL = {
    "mean": "average", "median": "median", "min": "minimum", "max": "maximum",
    "sum": "sum", "count": "count", "nunique": "number of unique values", "std": "standard deviation",
    "percentile": "percentile",
}
OP_PREFIX = {
    "mean": "average", "median": "median", "min": "min", "max": "max",
    "sum": "sum", "count": "count", "nunique": "unique_count", "std": "std",
    "percentile": "percentile",
}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class ExecResult:
    answer: str
    explanation: str
    table: TableData | None = None
    chart: ChartSpec | None = None
    stat: StatCard | None = None


# ---------------------------------------------------------------- helpers

def df_to_table(df: pd.DataFrame, max_rows: int = MAX_TABLE_ROWS) -> TableData:
    shown = df.head(max_rows).copy()
    for col in shown.columns:
        if pd.api.types.is_datetime64_any_dtype(shown[col]):
            midnight = (shown[col].dropna().dt.normalize() == shown[col].dropna()).all()
            shown[col] = shown[col].dt.strftime("%Y-%m-%d" if midnight else "%Y-%m-%d %H:%M")
    rows = [[to_py(v) for v in row] for row in shown.itertuples(index=False, name=None)]
    return TableData(columns=[str(c) for c in shown.columns], rows=rows, total_rows=len(df), truncated=len(df) > max_rows)


def describe_conditions(conditions: list[Condition], logic: str = "and") -> str:
    parts = []
    for c in conditions:
        if c.operator in ("is_null", "not_null"):
            parts.append(f"{c.column} {'is missing' if c.operator == 'is_null' else 'is present'}")
        elif c.operator == "between":
            parts.append(f"{c.column} is between {c.value[0]} and {c.value[1]}")
        elif c.operator in ("starts_with", "ends_with"):
            parts.append(f"{c.column} {c.operator.replace('_', ' ')} '{c.value}'")
        else:
            value = c.value if not isinstance(c.value, list) else ", ".join(map(str, c.value))
            shown = fmt_num(value) if isinstance(value, float) else value
            if isinstance(shown, str) and shown.endswith("T00:00:00"):
                shown = shown[:-9]
            op = {"in": "is one of", "not_in": "is not one of"}.get(c.operator, c.operator)
            parts.append(f"{c.column} {op} {shown}")
    return f" {logic} ".join(parts)


def _condition_mask(df: pd.DataFrame, c: Condition) -> pd.Series:
    s = df[c.column]
    op, v = c.operator, c.value
    if op == "is_null":
        return s.isna()
    if op == "not_null":
        return s.notna()
    if pd.api.types.is_datetime64_any_dtype(s):
        v = [pd.Timestamp(i) for i in v] if isinstance(v, list) else pd.Timestamp(v)
    if op == "between":
        return ((s >= v[0]) & (s <= v[1])).fillna(False)
    if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s) or pd.api.types.is_bool_dtype(s):
        compare = {
            "==": lambda: s == v, "!=": lambda: s != v, ">": lambda: s > v, ">=": lambda: s >= v,
            "<": lambda: s < v, "<=": lambda: s <= v,
            "in": lambda: s.isin(v), "not_in": lambda: ~s.isin(v),
        }
        return compare[op]().fillna(False)
    text = s.astype(str).str.strip().str.lower().where(s.notna())
    if op == "==":
        return (text == str(v).lower()).fillna(False)
    if op == "!=":
        return (text != str(v).lower()).where(s.notna(), False)
    if op == "contains":
        return text.str.contains(str(v).lower(), regex=False, na=False)
    if op == "starts_with":
        return text.str.startswith(str(v).lower(), na=False)
    if op == "ends_with":
        return text.str.endswith(str(v).lower(), na=False)
    values = {str(i).lower() for i in v}
    return text.isin(values) if op == "in" else (~text.isin(values)).where(s.notna(), False)


def apply_conditions(df: pd.DataFrame, conditions: list[Condition], logic: str = "and") -> pd.DataFrame:
    if not conditions:
        return df
    masks = [_condition_mask(df, c) for c in conditions]
    combined = masks[0]
    for m in masks[1:]:
        combined = (combined | m) if logic == "or" else (combined & m)
    return df[combined]


def where_text(conditions: list[Condition], logic: str = "and") -> str:
    return f" where {describe_conditions(conditions, logic)}" if conditions else ""


def no_rows(conditions: list[Condition], logic: str = "and") -> ExecResult:
    return ExecResult(
        answer=f"No rows match{where_text(conditions, logic)}. Try loosening the filter.",
        explanation=f"Filtered the dataset{where_text(conditions, logic)}; the result was empty.",
    )


def ordinal(n: float) -> str:
    n = int(n) if float(n).is_integer() else n
    if isinstance(n, int):
        suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"
    return f"{n}th"


def op_label(plan: AnalysisPlan) -> str:
    return f"{ordinal(plan.percentile)} percentile" if plan.operation == "percentile" and plan.percentile is not None else OP_LABEL[plan.operation]


def compute(s: pd.Series, op: str, q: float | None = None):
    s = s.dropna()
    if op == "percentile":
        return None if s.empty else s.quantile((q or 0) / 100)
    if op == "count":
        return len(s)
    if op == "nunique":
        return s.nunique()
    if s.empty:
        return None
    return {"mean": s.mean, "median": s.median, "min": s.min, "max": s.max, "sum": s.sum, "std": s.std}[op]()


def make_chart(kind: str, title: str, x: str, y: str, data: pd.DataFrame | list[dict]) -> ChartSpec:
    records = data.to_dict("records") if isinstance(data, pd.DataFrame) else data
    return ChartSpec(type=kind, title=title, xAxis=x, yAxis=y, data=[to_py(r) for r in records])


def pick_chart_type(plan: AnalysisPlan, allowed: set[str], default: str) -> str:
    requested = plan.chart.type if plan.chart else None
    return requested if requested in allowed else default


def label_column(profile: DatasetProfile) -> str | None:
    """A human-readable row label (e.g. a 'name' column) if the dataset has one."""
    for c in profile.column_profiles:
        if c.kind == "categorical" and profile.rows and c.unique / profile.rows > 0.5:
            return c.name
    return None


def group_key(s: pd.Series, grain: str | None) -> pd.Series:
    if grain is None:
        return s
    fmt = {"year": "%Y", "month": "%Y-%m", "day": "%Y-%m-%d", "weekday": "%A"}[grain]
    return s.dt.strftime(fmt)


def strength(r: float) -> str:
    a = abs(r)
    word = "very weak" if a < 0.2 else "weak" if a < 0.4 else "moderate" if a < 0.6 else "strong" if a < 0.8 else "very strong"
    return word if a < 0.2 else f"{word} {'positive' if r > 0 else 'negative'}"


# ---------------------------------------------------------------- intents

def run_row_count(df, plan, profile):
    return ExecResult(
        f"The dataset has {len(df):,} rows.", "Counted the rows of the dataframe.",
        stat=StatCard(label="Rows", value=f"{len(df):,}"),
    )


def run_column_count(df, plan, profile):
    return ExecResult(
        f"The dataset has {len(df.columns)} columns.", "Counted the columns of the dataframe.",
        stat=StatCard(label="Columns", value=str(len(df.columns))),
    )


def run_list_columns(df, plan, profile):
    table = pd.DataFrame(
        [(c.name, c.kind, c.missing, c.unique) for c in profile.column_profiles],
        columns=["column", "type", "missing", "unique_values"],
    )
    return ExecResult(
        f"The dataset has {len(df.columns)} columns: {', '.join(df.columns)}.",
        "Listed the column names with their detected types.", table=df_to_table(table),
    )


def run_aggregation(df, plan, profile):
    sub = apply_conditions(df, plan.conditions, plan.condition_logic)
    scope = where_text(plan.conditions, plan.condition_logic)
    if sub.empty:
        return no_rows(plan.conditions, plan.condition_logic)
    op, col = plan.operation, plan.column
    if col is None:
        return ExecResult(
            f"There are {len(sub):,} rows{scope}.", f"Counted the rows{scope}.",
            stat=StatCard(label="Rows", value=f"{len(sub):,}"),
        )
    value = compute(sub[col], op, plan.percentile)
    if value is None:
        raise PlanError(f"The '{col}' column has no values to calculate the {op_label(plan)} from.")
    shown = value.strftime("%Y-%m-%d") if isinstance(value, pd.Timestamp) else fmt_num(value)
    return ExecResult(
        f"The {op_label(plan)} of {col} is {shown}{scope}.",
        f"Calculated the {op_label(plan)} of the '{col}' column{scope} (missing values ignored).",
        stat=StatCard(label=f"{op_label(plan).capitalize()} {col}".replace("Count ", "Count of "), value=shown),
    )


def metric_noun(plan: AnalysisPlan) -> str:
    if not plan.target_column:
        return "number of rows"
    label = op_label(plan)
    target = plan.target_column
    return target if label.split()[0] in target.lower() else f"{label} {target}"


MAX_PIVOT_COLUMNS = 12


def run_groupby(df, plan, profile):
    sub = apply_conditions(df, plan.conditions, plan.condition_logic)
    if sub.empty:
        return no_rows(plan.conditions, plan.condition_logic)
    group, group2, target, op, grain = plan.group_by, plan.group_by_2, plan.target_column, plan.operation, plan.date_grain
    label = op_label(plan)
    keyed = sub.assign(_key=group_key(sub[group], grain))
    keys = ["_key"] + ([group2] if group2 else [])
    if target:
        result = keyed.groupby(keys)[target].agg(lambda s: compute(s, op, plan.percentile))
        out_name = target if OP_PREFIX[op] in target.lower() else f"{OP_PREFIX[op]}_{target}"
        if op == "sum" and out_name == target:
            out_name = f"sum_{target}"
        if op == "percentile":
            out_name = f"p{int(plan.percentile) if float(plan.percentile).is_integer() else plan.percentile}_{target}"
    else:
        result = keyed.groupby(keys).size()
        out_name = "count"
    result = pd.to_numeric(result, errors="coerce").dropna()
    if result.empty:
        raise PlanError(f"No values were available to calculate the {label} by {group}.")
    table = result.rename(out_name).reset_index().rename(columns={"_key": group})
    is_date = grain is not None
    if is_date and plan.order is None:
        table = table.sort_values(group, key=(lambda s: s.map(WEEKDAYS.index)) if grain == "weekday" else None, kind="stable")
        descending = True
    else:
        descending = plan.order != "asc"
        table = table.sort_values(out_name, ascending=not descending, kind="stable")
    table[out_name] = table[out_name].round(2)
    label_cols = [group] + ([group2] if group2 else [])
    limit = plan.limit
    shown = table.head(limit if limit and limit > 1 else 10 if limit == 1 else MAX_TABLE_ROWS)
    top = table.iloc[0]
    top_label = " / ".join(str(top[c]) for c in label_cols)
    noun = metric_noun(plan)
    scope = where_text(plan.conditions, plan.condition_logic)
    by_text = " and ".join(label_cols)
    if limit == 1:
        superlative = ("highest" if descending else "lowest") if target else ("most" if descending else "fewest")
        answer = (f"{top_label} has the {superlative} {noun} at {fmt_num(top[out_name])}{scope}."
                  if target else f"{top_label} has the {superlative} rows ({fmt_num(top[out_name])}){scope}.")
    elif is_date:
        best = table.loc[table[out_name].idxmax()]
        answer = (f"Calculated the {noun} for {len(table)} {grain} periods{scope}. "
                  f"Peak: {best[group]} ({fmt_num(best[out_name])}).")
    else:
        by_value = table.sort_values(out_name, ascending=False, kind="stable")
        hi, lo = by_value.iloc[0], by_value.iloc[-1]
        hi_label = " / ".join(str(hi[c]) for c in label_cols)
        lo_label = " / ".join(str(lo[c]) for c in label_cols)
        answer = (f"Calculated the {noun} for {len(table)} {by_text} groups{scope}. "
                  f"Highest: {hi_label} ({fmt_num(hi[out_name])}); lowest: {lo_label} ({fmt_num(lo[out_name])}).")
    grain_text = f" ({grain})" if grain else ""
    explanation = (f"Grouped the dataset by {by_text}{grain_text}{scope} and calculated the {label} "
                   f"of {target or 'row counts'}, sorted {'descending' if descending else 'ascending'}"
                   f"{' by value' if not (is_date and plan.order is None) else ' chronologically'}.")

    # Two categories -> a pivot table (rows x columns) with a grouped chart, unless the user opted out.
    if group2 and not is_date and plan.pivot is not False and table[group2].nunique() <= MAX_PIVOT_COLUMNS:
        wide = table.pivot_table(index=group, columns=group2, values=out_name, aggfunc="first")
        wide.columns = [str(c) for c in wide.columns]
        wide = wide.loc[wide.mean(axis=1, skipna=True).sort_values(ascending=not descending, kind="stable").index]
        wide = wide.head(limit if limit and limit > 1 else MAX_CHART_GROUPS)
        flat = wide.reset_index()
        explanation += f" Arranged as a pivot table: {group} down the side, {group2} across the top."
        series = [str(c) for c in wide.columns]
        wants = (plan.chart.type if plan.chart and plan.chart.type in ("bar", "line", "area") else "bar")
        chart = make_chart(wants, f"{noun.capitalize()} by {by_text}".replace("Number of rows", "Row count"), group, series[0], flat)
        chart.series = series
        return ExecResult(answer, explanation, table=df_to_table(flat), chart=chart)

    chart = None
    wants_chart = plan.chart and plan.chart.required
    if 2 <= len(shown) <= MAX_CHART_GROUPS or (wants_chart and len(shown) >= 1):
        default = "line" if is_date else "bar"
        kind = pick_chart_type(plan, {"bar", "line", "pie", "area"}, default)
        title = f"{noun.capitalize()} by {by_text}".replace("Number of rows", "Row count")
        data = shown.head(MAX_CHART_GROUPS)
        x_axis = group
        if group2:  # one bar per combination
            data = data.assign(**{"group": data[group].astype(str) + " / " + data[group2].astype(str)})[["group", out_name]]
            x_axis = "group"
        chart = make_chart(kind, title, x_axis, out_name, data)
    return ExecResult(answer, explanation, table=df_to_table(shown), chart=chart)


def run_filter(df, plan, profile):
    sub = apply_conditions(df, plan.conditions, plan.condition_logic)
    if sub.empty:
        return no_rows(plan.conditions, plan.condition_logic)
    if plan.sort_by:
        sub = sub.sort_values(plan.sort_by, ascending=plan.order == "asc", na_position="last", kind="stable")
    if plan.columns:
        sub = sub[plan.columns]
    total = len(sub)
    if plan.limit:
        sub = sub.head(plan.limit)
    scope = where_text(plan.conditions, plan.condition_logic)
    if plan.conditions:
        answer = f"Found {total:,} matching rows{scope}."
        explanation = f"Filtered the dataset{scope}."
    else:
        answer = f"Showing the first {len(sub):,} of {len(df):,} rows."
        explanation = "Returned rows from the top of the dataset."
    if len(sub) > MAX_TABLE_ROWS:
        answer += f" Displaying the first {MAX_TABLE_ROWS}."
    chart = _table_chart(plan, sub)
    return ExecResult(answer, explanation, table=df_to_table(sub), chart=chart)


def _table_chart(plan: AnalysisPlan, table: pd.DataFrame) -> ChartSpec | None:
    """Only chart a row-level table when the user explicitly asked for it."""
    req = plan.chart
    if not (req and req.required and req.x in table.columns and req.y in table.columns):
        return None
    kind = pick_chart_type(plan, {"bar", "line", "pie", "area", "scatter"}, "bar")
    return make_chart(kind, f"{req.y} by {req.x}", req.x, req.y, table[[req.x, req.y]].head(MAX_CHART_POINTS))


def run_top_bottom(df, plan, profile):
    bottom = plan.intent == "bottom_n"
    col, n = plan.column, plan.limit or 10
    sub = apply_conditions(df, plan.conditions, plan.condition_logic).dropna(subset=[col])
    if sub.empty:
        return no_rows(plan.conditions, plan.condition_logic)
    if plan.percent:
        n = max(1, math.ceil(len(sub) * plan.percent / 100))
    sub = sub.sort_values(col, ascending=bottom, kind="stable").head(n)
    if plan.columns:
        sub = sub[plan.columns if col in plan.columns else [*plan.columns, col]]
    label = label_column(profile)
    first = sub.iloc[0]
    lead = f"{first[label]} ({fmt_num(first[col])})" if label and label in sub.columns else fmt_num(first[col])
    scope = where_text(plan.conditions, plan.condition_logic)
    extreme = "Lowest" if bottom else "Highest"
    if plan.percent:
        answer = (f"Here are the {'bottom' if bottom else 'top'} {fmt_num(plan.percent)}% by {col} "
                  f"({len(sub)} rows){scope}. {extreme}: {lead}.")
        explanation = (f"Sorted by {col} ({'ascending' if bottom else 'descending'}){scope} and kept the "
                       f"{'bottom' if bottom else 'top'} {fmt_num(plan.percent)}% of rows ({len(sub)} of the rows that have a value).")
    elif len(sub) == 1:
        answer = f"The {extreme.lower()} {col}{scope} is {lead}."
        explanation = f"Sorted the dataset by {col} in {'ascending' if bottom else 'descending'} order{scope} and kept the first row."
    else:
        answer = f"Here are the {'bottom' if bottom else 'top'} {len(sub)} rows by {col}{scope}. {extreme}: {lead}."
        explanation = f"Sorted the dataset by {col} in {'ascending' if bottom else 'descending'} order{scope} and kept the first {n} rows."
    return ExecResult(answer, explanation, table=df_to_table(sub), chart=_table_chart(plan, sub))


def run_rank(df, plan, profile):
    """Rank (1 = highest) and percentile of the matching row(s) among every row that has a value."""
    col = plan.column
    valid = df.dropna(subset=[col])
    ranks = valid[col].rank(method="min", ascending=False)
    matches = apply_conditions(valid, plan.conditions, plan.condition_logic)
    scope = describe_conditions(plan.conditions, plan.condition_logic)
    if matches.empty:
        return no_rows(plan.conditions, plan.condition_logic)
    total = len(valid)
    out = matches.head(20).copy()
    out["rank"] = ranks.loc[out.index].astype(int)
    out["of"] = total
    out["percentile"] = (100 * (valid[col].rank(method="max") .loc[out.index] / total)).round(1)
    label = label_column(profile)
    keep = ([label] if label and label in out.columns else []) + [col, "rank", "of", "percentile"]
    out = out[list(dict.fromkeys(keep))].sort_values("rank")
    first = out.iloc[0]
    who = str(first[label]) if label and label in out.columns else scope
    behind = 100 - first["percentile"]
    tail = "the highest value" if int(first["rank"]) == 1 else f"ahead of {behind:.0f}% of rows"
    answer = f"{who} ranks #{int(first['rank'])} of {total:,} by {col} ({fmt_num(first[col])}), {tail}."
    if len(matches) > 1:
        answer += f" {len(matches)} rows matched; the best-ranked is shown first."
    return ExecResult(
        answer,
        f"Ranked all {total:,} rows with a value in '{col}' from highest (1) to lowest, then looked up rows where {scope}. "
        "Ties share the best rank.",
        table=df_to_table(out), stat=StatCard(label=f"Rank by {col}", value=f"#{int(first['rank'])}"),
    )


def _iqr_bounds(s: pd.Series) -> tuple[float, float]:
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    return float(q1 - 1.5 * iqr), float(q3 + 1.5 * iqr)


def run_outliers(df, plan, profile):
    """Rows outside the 1.5 x IQR fences of a numeric column (or a per-column summary if none is given)."""
    sub = apply_conditions(df, plan.conditions, plan.condition_logic)
    scope = where_text(plan.conditions, plan.condition_logic)
    ids = {c.name for c in profile.column_profiles if c.is_identifier}
    if plan.column:
        col = plan.column
        s = sub[col].dropna()
        if len(s) < 4:
            raise PlanError(f"'{col}' has too few values to look for outliers.")
        lo, hi = _iqr_bounds(s)
        if hi == lo:
            raise PlanError(f"'{col}' has almost no spread, so outliers can't be defined.")
        found = sub[(sub[col] < lo) | (sub[col] > hi)].copy()
        explanation = (f"Used the 1.5 × IQR rule on '{col}'{scope}: values below {fmt_num(lo)} or above {fmt_num(hi)} "
                       "are flagged as outliers.")
        if found.empty:
            return ExecResult(f"No outliers found in {col}{scope} (typical range {fmt_num(lo)} to {fmt_num(hi)}).", explanation,
                              stat=StatCard(label=f"Outliers in {col}", value="0"))
        found["_dist"] = (found[col] - found[col].clip(lo, hi)).abs()
        found = found.sort_values("_dist", ascending=False).drop(columns="_dist")
        answer = (f"Found {len(found):,} outlier{'s' if len(found) != 1 else ''} in {col}{scope}: values outside "
                  f"{fmt_num(lo)} to {fmt_num(hi)}. Most extreme: {fmt_num(found.iloc[0][col])}.")
        return ExecResult(answer, explanation, table=df_to_table(found), stat=StatCard(label=f"Outliers in {col}", value=f"{len(found):,}"))

    rows = []
    for col in [c for c in profile.numeric_columns if c not in ids]:
        s = sub[col].dropna()
        if len(s) < 4:
            continue
        lo, hi = _iqr_bounds(s)
        if hi == lo:
            continue
        n = int(((s < lo) | (s > hi)).sum())
        rows.append({"column": col, "outliers": n, "lower_fence": round(lo, 2), "upper_fence": round(hi, 2)})
    if not rows:
        raise PlanError("There are no numeric columns with enough spread to look for outliers.")
    table = pd.DataFrame(rows).sort_values("outliers", ascending=False, kind="stable")
    total = int(table["outliers"].sum())
    if total == 0:
        return ExecResult(
            f"No outliers found in any of the {len(table)} numeric columns{scope} (1.5 × IQR rule).",
            "Used the 1.5 × IQR rule on every numeric column.", table=df_to_table(table), stat=StatCard(label="Outlying values", value="0"),
        )
    return ExecResult(
        f"Found {total:,} outlying values across {int((table['outliers'] > 0).sum())} numeric column(s){scope}. "
        "Ask about one column (for example 'show the outliers in <column>') to see the rows.",
        "Used the 1.5 × IQR rule on every numeric column.", table=df_to_table(table),
        stat=StatCard(label="Outlying values", value=f"{total:,}"),
    )


def run_unique_values(df, plan, profile):
    col = plan.column
    sub = apply_conditions(df, plan.conditions, plan.condition_logic)
    values = sub[col].dropna().drop_duplicates()
    try:
        values = values.sort_values()
    except TypeError:
        pass
    preview = ", ".join(map(str, values.head(10).tolist()))
    more = f" (and {len(values) - 10} more)" if len(values) > 10 else ""
    return ExecResult(
        f"'{col}' has {len(values):,} unique values: {preview}{more}." if len(values) else f"'{col}' has no values.",
        f"Found the distinct non-missing values of '{col}'.",
        table=df_to_table(values.to_frame(col)), stat=StatCard(label=f"Unique {col}", value=f"{len(values):,}"),
    )


def run_value_counts(df, plan, profile):
    col = plan.column
    sub = apply_conditions(df, plan.conditions, plan.condition_logic)
    series = sub[col].dropna().astype(str)
    if series.empty:
        return no_rows(plan.conditions, plan.condition_logic)
    counts = series.value_counts()
    if plan.order == "asc":
        counts = counts.sort_values(kind="stable")
    total = int(counts.sum())
    table = counts.rename("count").rename_axis(col).reset_index()
    table["percent"] = (100 * table["count"] / total).round(2)
    shown = table.head(plan.limit or 20)
    top = table.iloc[0]
    answer = (f"{'Least' if plan.order == 'asc' else 'Most'} common {col}: {top[col]} "
              f"({int(top['count'])} rows, {top['percent']:.1f}%). There are {len(table)} distinct values.")
    chart = None
    if 2 <= len(shown) <= 30:
        chart = make_chart(pick_chart_type(plan, {"bar", "pie"}, "bar"), f"Count of {col}", col, "count", shown[[col, "count"]])
    return ExecResult(answer, f"Counted how often each value of '{col}' occurs{where_text(plan.conditions, plan.condition_logic)}.",
                      table=df_to_table(shown), chart=chart)


def run_missing(df, plan, profile):
    cols = [plan.column] if plan.column else list(df.columns)
    counts = df[cols].isna().sum()
    total = int(counts.sum())
    if plan.column:
        pct = 100 * total / len(df)
        return ExecResult(
            f"'{plan.column}' has {total:,} missing values ({pct:.1f}% of rows).",
            f"Counted empty cells in '{plan.column}'.", stat=StatCard(label=f"Missing in {plan.column}", value=f"{total:,}"),
        )
    missing = counts[counts > 0].sort_values(ascending=False)
    if missing.empty:
        return ExecResult("There are no missing values in this dataset.", "Counted empty cells in every column.",
                          stat=StatCard(label="Missing values", value="0"))
    table = missing.rename("missing").rename_axis("column").reset_index()
    table["percent"] = (100 * table["missing"] / len(df)).round(2)
    chart = make_chart("bar", "Missing values by column", "column", "missing", table[["column", "missing"]]) if len(table) >= 2 else None
    return ExecResult(
        f"Yes, there are {total:,} missing values across {len(missing)} column(s): "
        + ", ".join(f"{k} ({v})" for k, v in missing.items()) + ".",
        "Counted empty cells in every column.", table=df_to_table(table), chart=chart,
        stat=StatCard(label="Missing values", value=f"{total:,}"),
    )


def _scatter(df: pd.DataFrame, x: str, y: str) -> list[dict]:
    pairs = df[[x, y]].dropna()
    if len(pairs) > MAX_CHART_POINTS:
        pairs = pairs.sample(MAX_CHART_POINTS, random_state=0)
    return pairs.to_dict("records")


def run_correlation(df, plan, profile):
    sub = apply_conditions(df, plan.conditions, plan.condition_logic)
    scope = where_text(plan.conditions, plan.condition_logic)
    if plan.x_column:
        x, y = plan.x_column, plan.y_column
        pairs = sub[[x, y]].dropna()
        if len(pairs) < 3:
            raise PlanError("There are fewer than 3 complete rows for these columns, so a correlation can't be computed.")
        if pairs[x].nunique() < 2 or pairs[y].nunique() < 2:
            raise PlanError("One of the columns is constant, so a correlation can't be computed.")
        r = float(pairs[x].corr(pairs[y]))
        return ExecResult(
            f"The Pearson correlation between {x} and {y} is {r:.2f} ({strength(r)}){scope}, based on {len(pairs):,} rows.",
            f"Computed the Pearson correlation of '{x}' and '{y}' on rows where both are present{scope}.",
            chart=make_chart("scatter", f"{y} vs {x}", x, y, _scatter(sub, x, y)),
            stat=StatCard(label=f"Correlation ({x}, {y})", value=f"{r:.2f}"),
        )
    ids = {c.name for c in profile.column_profiles if c.is_identifier}
    numeric = [c for c in profile.numeric_columns if c not in ids]
    if len(numeric) < 2:
        raise PlanError("I need at least two numeric columns to compute correlations, and this dataset doesn't have them.")
    matrix = sub[numeric].corr()
    best, best_r = None, 0.0
    for i, a in enumerate(numeric):
        for b in numeric[i + 1:]:
            r = matrix.loc[a, b]
            if pd.notna(r) and abs(r) >= abs(best_r):
                best, best_r = (a, b), float(r)
    if best is None:
        raise PlanError("Correlations could not be computed for the numeric columns.")
    table = matrix.round(2).rename_axis("column").reset_index()
    return ExecResult(
        f"Strongest relationship: {best[0]} and {best[1]} (r = {best_r:.2f}, {strength(best_r)}).",
        f"Computed the Pearson correlation matrix of {len(numeric)} numeric columns{scope}.",
        table=df_to_table(table), chart=make_chart("scatter", f"{best[1]} vs {best[0]}", best[0], best[1], _scatter(sub, *best)),
        stat=StatCard(label=f"Correlation ({best[0]}, {best[1]})", value=f"{best_r:.2f}"),
    )


def run_distribution(df, plan, profile):
    col = plan.column
    series = apply_conditions(df, plan.conditions, plan.condition_logic)[col].dropna()
    if series.empty:
        raise PlanError(f"'{col}' has no values to build a distribution from.")
    bins = plan.bins or (min(10, max(series.nunique(), 2)))
    counts, edges = np.histogram(series, bins=bins)
    labels = [f"{fmt_num(edges[i])}–{fmt_num(edges[i + 1])}" for i in range(len(counts))]
    table = pd.DataFrame({"range": labels, "count": counts})
    table["percent"] = (100 * table["count"] / len(series)).round(2)
    peak = table.loc[table["count"].idxmax()]
    answer = (f"{col} ranges from {fmt_num(series.min())} to {fmt_num(series.max())} "
              f"(mean {fmt_num(series.mean())}, median {fmt_num(series.median())}, std {fmt_num(series.std())}). "
              f"Most values ({int(peak['count'])}) fall in {peak['range']}.")
    return ExecResult(
        answer, f"Split '{col}' into {len(counts)} equal-width bins and counted the rows in each.",
        table=df_to_table(table), chart=make_chart("histogram", f"Distribution of {col}", "range", "count", table[["range", "count"]]),
    )


def run_percentage(df, plan, profile):
    matched = int(len(apply_conditions(df, plan.conditions, plan.condition_logic)))
    total = len(df)
    pct = 100 * matched / total if total else 0.0
    desc = describe_conditions(plan.conditions, plan.condition_logic)
    return ExecResult(
        f"{matched:,} of {total:,} rows ({pct:.2f}%) match {desc}.",
        f"Counted rows where {desc} and divided by the total number of rows ({total:,}).",
        stat=StatCard(label=f"Share where {desc}", value=f"{pct:.2f}%"),
    )


def run_describe(df, plan, profile):
    if plan.column:
        s = apply_conditions(df, plan.conditions, plan.condition_logic)[plan.column]
        stats = s.describe()
        table = pd.DataFrame({"statistic": stats.index.astype(str), "value": [to_py(v) for v in stats.values]})
        table["value"] = table["value"].map(lambda v: round(v, 2) if isinstance(v, float) else v)
        return ExecResult(f"Summary statistics for {plan.column}.", f"Ran a descriptive summary of '{plan.column}'.", table=df_to_table(table))
    ids = {c.name for c in profile.column_profiles if c.is_identifier}
    numeric = [c for c in profile.numeric_columns if c not in ids]
    if not numeric:
        raise PlanError("There are no numeric columns to summarise. Ask about a specific column instead.")
    stats = df[numeric].describe().T.round(2).rename_axis("column").reset_index()
    return ExecResult("Summary statistics for the numeric columns.", "Ran a descriptive summary of all numeric columns.", table=df_to_table(stats))


HANDLERS: dict[str, Callable] = {
    "row_count": run_row_count,
    "column_count": run_column_count,
    "list_columns": run_list_columns,
    "aggregation": run_aggregation,
    "groupby_aggregation": run_groupby,
    "filter": run_filter,
    "top_n": run_top_bottom,
    "bottom_n": run_top_bottom,
    "unique_values": run_unique_values,
    "value_counts": run_value_counts,
    "missing_values": run_missing,
    "correlation": run_correlation,
    "distribution": run_distribution,
    "percentage": run_percentage,
    "describe": run_describe,
    "rank": run_rank,
    "outliers": run_outliers,
}


def execute_plan(df: pd.DataFrame, plan: AnalysisPlan, profile: DatasetProfile) -> ExecResult:
    handler = HANDLERS.get(plan.intent)
    if handler is None:
        raise PlanError(f"The operation '{plan.intent}' is not supported.", status="unsupported")
    return handler(df, plan, profile)

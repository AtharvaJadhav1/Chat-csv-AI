"""Rule-based planner used when no LLM API key is configured.

It produces exactly the same structured AnalysisPlan as the LLM planner, so the
validator and executor pipeline is identical. It is deterministic, offline, and
only understands the common question shapes listed in the README.
"""
import re

from ..models.dataset import DatasetRecord
from ..schemas.api import ColumnProfile
from ..schemas.plan import AnalysisPlan, ChartRequest, Condition

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
STAT_WORDS = {
    "mean": r"\b(average|avg|mean)\b", "median": r"\bmedian\b", "sum": r"\b(total|sum)\b",
    "max": r"\b(maximum|max)\b", "min": r"\b(minimum|min)\b", "std": r"\b(standard deviation|std)\b",
}
DESC_WORDS = r"\b(highest|most|best|top|largest|biggest|maximum|greatest|higher|oldest)\b"
ASC_WORDS = r"\b(lowest|least|fewest|worst|bottom|smallest|minimum|lower|youngest)\b"
ROW_NOUNS = {"rows", "records", "entries", "students", "people", "items", "observations", "customers", "employees", "persons", "users", "data", "orders"}
GENERIC = r"\b(rows?|records?|entries|columns?|fields?|dataset|csv|how many|number of|count|missing|null|total|average|mean|median|sum|maximum|minimum|outliers?|anomal\w+|percentile|quartile)\b"
ANALYTIC = r"\b(show|list|find|display|give|get|how many|count|number of|which|who|percent|percentage|average|total|best|worst|top|bottom|highest|lowest|compare)\b"
STOP_TOKENS = {"of", "the", "a", "an", "by", "per", "in", "for", "number", "all", "each", "is", "are", "there", "and", "to", "from", "with", "any", "value", "values"}
METRIC_SYNONYMS = r"\b(sales|revenue|income|turnover|earnings)\b"
METRIC_COLUMN_HINTS = ("amount", "revenue", "sales", "total", "income", "price", "value")
ISO_DATE = r"\d{4}-\d{2}-\d{2}"


def _variants(name: str) -> list[str]:
    spaced = name.lower().replace("_", " ")
    return list({spaced, name.lower()})


def _phrase_pattern(name: str) -> str:
    parts = []
    for v in _variants(name):
        if v.endswith("y") and len(v) > 3:
            parts.append(re.escape(v[:-1]) + "(?:y|ies)")
        elif v.endswith("s") and len(v) > 3:
            parts.append(re.escape(v[:-1]) + "(?:s|es)?")
        else:
            parts.append(re.escape(v) + "(?:s|es)?")
    return r"\b(?:" + "|".join(parts) + r")\b"


def _mentions(q: str, cols: list[ColumnProfile]) -> tuple[list[ColumnProfile], str]:
    """Columns referenced in the question (in order) and the question with those phrases removed."""
    found: list[tuple[int, ColumnProfile]] = []
    stripped = q
    for c in cols:
        m = re.search(_phrase_pattern(c.name), q)
        if m:
            found.append((m.start(), c))
            stripped = re.sub(_phrase_pattern(c.name), " ", stripped)
    return [c for _, c in sorted(found, key=lambda t: t[0])], stripped


NEGATION = re.compile(r"\b(?:not|except|excluding|exclude|other than|outside|without|apart from)\b(?:\s+[a-z0-9]+){0,3}?\s*(?:or\s+|and\s+)?$")


def _value_conditions(q: str, record: DatasetRecord) -> list[Condition]:
    conditions: list[Condition] = []
    df = record.df
    for c in record.profile.column_profiles:
        if c.kind != "categorical" or c.unique > 100 or (record.profile.rows and c.unique / record.profile.rows > 0.5):
            continue
        plain, negated = [], []
        for v in df[c.name].dropna().astype(str).unique():
            if len(v) < 2 or v.replace(".", "").isdigit() or v.lower() not in q:
                continue
            m = re.search(rf"(?<![a-z0-9]){re.escape(v.lower())}(?![a-z0-9])", q)
            if m:
                (negated if NEGATION.search(q[max(0, m.start() - 40):m.start()]) else plain).append(v)
        for hits, eq, many in ((plain, "==", "in"), (negated, "!=", "not_in")):
            if len(hits) == 1:
                conditions.append(Condition(column=c.name, operator=eq, value=hits[0]))
            elif hits:
                conditions.append(Condition(column=c.name, operator=many, value=hits))
    return conditions


def _entity_conditions(q: str, record: DatasetRecord) -> list[Condition]:
    """Exact matches of a full value from a high-cardinality text column (e.g. a person's name)."""
    out: list[Condition] = []
    for c in record.profile.column_profiles:
        if c.kind != "categorical" or not record.profile.rows or c.unique / record.profile.rows <= 0.5:
            continue
        for v in record.df[c.name].dropna().astype(str).unique():
            if len(v) >= 3 and v.lower() in q and re.search(rf"(?<![a-z0-9]){re.escape(v.lower())}(?![a-z0-9])", q):
                out.append(Condition(column=c.name, operator="==", value=v))
                break
    return out


def _text_conditions(q: str, mentioned: list[ColumnProfile], cols: list[ColumnProfile]) -> list[Condition]:
    """'name starts with A', 'city ends with ore', 'product containing chair'."""
    text_cols = [c for c in cols if c.kind == "categorical"]
    target = next((c for c in mentioned if c.kind == "categorical"), None) or next(
        (c for c in text_cols if "name" in c.name.lower()), None) or (text_cols[0] if text_cols else None)
    if target is None:
        return []
    out: list[Condition] = []
    word = r"(?:the\s+(?:letter\s+)?)?['\"]?([a-z0-9]+)"
    for pattern, op in (
        (rf"\b(?:start|starts|starting|begin|begins|beginning)\s+with\s+{word}", "starts_with"),
        (rf"\b(?:end|ends|ending)\s+with\s+{word}", "ends_with"),
        (rf"\b(?:contain|contains|containing)\s+{word}", "contains"),
    ):
        m = re.search(pattern, q)
        if m:
            out.append(Condition(column=target.name, operator=op, value=m.group(1)))
    return out


def _wants_or(q: str, conditions: list[Condition], cols: list[ColumnProfile]) -> bool:
    """True for 'marks above 90 or attendance below 60' (different conditions joined by OR)."""
    if len(conditions) < 2 or len({c.column for c in conditions}) < 2 or not re.search(r"\bor\b", q):
        return False
    keywords = r"(?:above|below|over|under|more than|less than|greater|fewer|at least|at most|older|younger|between|starts?|ends?|contains?)"
    names = "|".join(_phrase_pattern(c.name) for c in cols)
    values = [re.escape(str(c.value).lower()) for c in conditions if isinstance(c.value, str)]
    list_values = [re.escape(str(v).lower()) for c in conditions if c.operator in ("in", "not_in") for v in c.value]
    for m in re.finditer(r"\bor\b", q):
        tail = q[m.end():m.end() + 60]
        if list_values and re.match(rf"\s*(?:from\s+|in\s+)?(?:{'|'.join(list_values)})\b", tail):
            continue  # "Pune or Mumbai": two values of the same column
        words = " ".join(tail.split()[:6])
        if re.search(rf"\b{keywords}\b", words) or re.search(names, words):
            return True
        if values and re.match(rf"\s*(?:from\s+|in\s+|of\s+)?(?:{'|'.join(values)})", tail):
            return any(c.operator in (">", ">=", "<", "<=") for c in conditions)
    return False


def _numeric_conditions(q: str, numeric_mentions: list[ColumnProfile], extra_cols: list[ColumnProfile]) -> list[Condition]:
    num = r"(-?\d+(?:\.\d+)?)(?![\d-])\s*%?"
    rules = [
        (rf"\bbetween\s+{num}\s+and\s+{num}", None),
        (rf"(?:at least|no less than|greater than or equal to|>=)\s*{num}", ">="),
        (rf"(?:at most|no more than|less than or equal to|<=)\s*{num}", "<="),
        (rf"(?:below|under|less than|lower than|fewer than|smaller than|younger than|<)\s*{num}", "<"),
        (rf"(?:above|over|greater than|more than|higher than|older than|exceeds?|exceeding|>)\s*{num}", ">"),
        (rf"(?:equal to|equals|exactly|=)\s*{num}", "=="),
    ]
    conditions: list[Condition] = []
    for pattern, op in rules:
        m = re.search(pattern, q)
        if not m:
            continue
        col = None
        for c in reversed([c for c in numeric_mentions if _first_pos(q, c) < m.start()]):
            col = c
            break
        col = col or (numeric_mentions[0] if numeric_mentions else None)
        if col is None:  # "older than 22" -> an age column
            word = re.search(r"(older|younger) than", m.group(0))
            col = next((c for c in extra_cols if word and "age" in c.name.lower().split("_")), None)
        if col is None:
            continue
        if op is None:
            conditions += [Condition(column=col.name, operator=">=", value=float(m.group(1))),
                           Condition(column=col.name, operator="<=", value=float(m.group(2)))]
        else:
            conditions.append(Condition(column=col.name, operator=op, value=float(m.group(1))))
        q = q.replace(m.group(0), " ")
    return conditions


def _percentile(q: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:st|nd|rd|th)?\s*percentile", q)
    if m:
        return float(m.group(1))
    if re.search(r"\b(first|lower|1st)\s+quartile\b|\bq1\b", q):
        return 25.0
    if re.search(r"\b(second|2nd)\s+quartile\b|\bq2\b", q):
        return 50.0
    if re.search(r"\b(third|upper|3rd)\s+quartile\b|\bq3\b", q):
        return 75.0
    return None


def _first_pos(q: str, c: ColumnProfile) -> int:
    m = re.search(_phrase_pattern(c.name), q)
    return m.start() if m else 10**9


def _date_conditions(q: str, date_col: ColumnProfile | None) -> list[Condition]:
    if date_col is None:
        return []
    name = date_col.name
    m = re.search(rf"between\s+({ISO_DATE})\s+and\s+({ISO_DATE})", q)
    if m:
        return [Condition(column=name, operator=">=", value=m.group(1)), Condition(column=name, operator="<=", value=m.group(2))]
    out = []
    after = re.search(rf"(?:after|since|later than|from)\s+({ISO_DATE})", q)
    before = re.search(rf"(?:before|until|prior to|earlier than)\s+({ISO_DATE})", q)
    if after:
        out.append(Condition(column=name, operator=">=", value=after.group(1)))
    if before:
        out.append(Condition(column=name, operator="<", value=before.group(1)))
    return out


def _limit(q: str) -> int | None:
    m = re.search(r"\b(?:top|bottom|first|last|best|worst|lowest|highest)\s+(\d+)\b", q) or re.search(
        r"\b(\d+)\s+(?:lowest|highest|best|worst|top|bottom)\b", q)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(?:top|bottom|first|last|best|worst|lowest|highest)\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b", q)
    return NUMBER_WORDS[m.group(1)] if m else None


def _chart(q: str) -> ChartRequest | None:
    if not re.search(r"\b(chart|plot|graph|visuali[sz]e|visuali[sz]ation|histogram|pie|scatter|bar|line|trend)\b", q):
        return None
    kind = next((t for t, p in [("pie", r"\bpie\b"), ("line", r"\bline\b|\btrend\b"), ("scatter", r"\bscatter\b"),
                                ("histogram", r"\bhistogram\b"), ("area", r"\barea\b"), ("bar", r"\bbar\b")] if re.search(p, q)), None)
    return ChartRequest(required=True, type=kind)


def _stat_op(q: str) -> str | None:
    for op, pattern in STAT_WORDS.items():
        if re.search(pattern, q):
            return op
    return None


def _unsupported(profile_cols: list[ColumnProfile]) -> AnalysisPlan:
    names = ", ".join(c.name for c in profile_cols)
    return AnalysisPlan(
        intent="unsupported",
        message=f"I can't answer that from the uploaded dataset. It only contains these columns: {names}.",
    )


def plan_question(question: str, record: DatasetRecord) -> AnalysisPlan:
    plan = _plan_question(question, record)
    q = re.sub(r"\s+", " ", question.lower().strip())
    if _wants_or(q, plan.conditions, record.profile.column_profiles):
        plan = plan.model_copy(update={"condition_logic": "or"})
    return plan


def _plan_question(question: str, record: DatasetRecord) -> AnalysisPlan:
    profile = record.profile
    cols = profile.column_profiles
    ids = {c.name for c in cols if c.is_identifier}
    q = re.sub(r"\s+", " ", question.lower().strip().rstrip("?.!"))
    mentioned, q_no_cols = _mentions(q, cols)
    numeric_m = [c for c in mentioned if c.kind == "numeric" and c.name not in ids]
    synonym_metric = False
    if not numeric_m and re.search(METRIC_SYNONYMS, q):
        guess = next((c for h in METRIC_COLUMN_HINTS for c in cols if c.kind == "numeric" and c.name not in ids and h in c.name.lower()), None)
        if guess:
            numeric_m, mentioned, synonym_metric = [guess], [*mentioned, guess], True
    cat_m = [c for c in mentioned if c.kind in ("categorical", "boolean")]
    low_card = [c for c in cat_m if not profile.rows or c.unique / profile.rows <= 0.5]
    date_m = [c for c in mentioned if c.kind == "datetime"]
    only_date = next((c for c in cols if c.kind == "datetime"), None)
    value_conds = _value_conditions(q, record)
    num_conds = _numeric_conditions(q, numeric_m, cols)
    date_conds = _date_conditions(q, date_m[0] if date_m else only_date)
    ent_conds = _entity_conditions(q, record)
    text_conds = _text_conditions(q, mentioned, cols)
    conditions = value_conds + ent_conds + text_conds + num_conds + date_conds
    pct = _percentile(q)
    top_pct = re.search(r"\b(top|bottom|best|worst|highest|lowest)\s+(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)", q)
    pivot_word = bool(re.search(r"\bpivot|cross-?tab|matrix\b|\bgrid\b|breakdown", q))
    chart = _chart(q)
    op_all = _stat_op(q)  # "total amount by region" -> sum
    op = _stat_op(q_no_cols) or ("sum" if synonym_metric else None)  # "total amount over 5000" -> not a sum
    n = _limit(q)
    desc = bool(re.search(DESC_WORDS, q_no_cols))
    asc = bool(re.search(ASC_WORDS, q_no_cols))
    general = bool(re.search(GENERIC, q))
    analytic = bool(re.search(ANALYTIC, q)) or any(w in ROW_NOUNS for w in q.split())
    grain_m = re.search(r"\b(month(?:ly)?|year(?:ly)?|day|daily|weekday|week day)\b", q)

    # --- scope check: nothing in the question refers to this dataset
    if not mentioned and not general and not (value_conds and analytic) and not num_conds and not date_conds and not ent_conds and not text_conds and pct is None and not (grain_m and only_date):
        return _unsupported(cols)

    # --- dataset shape
    if re.search(r"\b(how many|number of|count of)\s+columns\b|\bcolumn count\b", q):
        return AnalysisPlan(intent="column_count")
    if re.search(r"\b(what|which|list|show|name)\b.*\b(columns|fields)\b|\bcolumns? (names|list)\b", q) and not mentioned:
        return AnalysisPlan(intent="list_columns")
    if re.search(r"\b(missing|null|nulls|empty|blank|nan)\b", q):
        return AnalysisPlan(intent="missing_values", column=mentioned[0].name if mentioned else None, chart=chart)

    # --- comparing named groups: "compare average X between North and South"
    in_cond = next((c for c in value_conds if c.operator == "in"), None)
    if in_cond and re.search(r"\b(compare|comparison|difference|versus|vs)\b", q) and numeric_m:
        return AnalysisPlan(intent="groupby_aggregation", group_by=in_cond.column, target_column=numeric_m[0].name,
                            operation=op or "mean", conditions=conditions, chart=chart)

    # --- outliers
    if re.search(r"outlier|anomal|unusual|extreme (?:value|row)", q):
        return AnalysisPlan(intent="outliers", column=numeric_m[0].name if numeric_m else None, conditions=conditions)

    # --- rank / standing of a specific row: "rank of Aarav Gupta by marks"
    if re.search(r"\b(rank|ranks|ranked|ranking|standing|position|where does .{1,40} stand)\b", q) and ent_conds:
        if not numeric_m:
            options = ", ".join(c for c in profile.numeric_columns if c not in ids)
            return AnalysisPlan(intent="clarification", message=f"Rank by which column? Numeric columns: {options}.")
        return AnalysisPlan(intent="rank", column=numeric_m[0].name, conditions=ent_conds)

    # --- top / bottom X percent of rows
    if top_pct:
        if not numeric_m:
            options = ", ".join(c for c in profile.numeric_columns if c not in ids)
            return AnalysisPlan(intent="clarification", message=f"Top {top_pct.group(2)}% by which column? Numeric columns: {options}.")
        bottom_words = top_pct.group(1) in ("bottom", "worst", "lowest")
        return AnalysisPlan(intent="bottom_n" if bottom_words else "top_n", column=numeric_m[0].name,
                            percent=float(top_pct.group(2)), conditions=conditions)

    # --- percentiles / quartiles
    if pct is not None:
        if not numeric_m:
            options = ", ".join(c for c in profile.numeric_columns if c not in ids)
            return AnalysisPlan(intent="clarification", message=f"Percentile of which column? Numeric columns: {options}.")
        if low_card and re.search(r"\b(by|per|each)\b", q):
            return AnalysisPlan(intent="groupby_aggregation", group_by=low_card[0].name, target_column=numeric_m[0].name,
                                operation="percentile", percentile=pct, conditions=conditions, chart=chart)
        return AnalysisPlan(intent="aggregation", operation="percentile", percentile=pct, column=numeric_m[0].name, conditions=conditions)

    # --- correlation
    if re.search(r"correlat|relationship|related|relation\b|associat|\bvs\b|versus|against", q):
        if len(numeric_m) >= 2:
            return AnalysisPlan(intent="correlation", x_column=numeric_m[0].name, y_column=numeric_m[1].name, conditions=value_conds)
        if not numeric_m:
            return AnalysisPlan(intent="correlation", conditions=value_conds)
        return AnalysisPlan(intent="clarification", message=f"Which second numeric column should I compare with {numeric_m[0].name}?")

    # --- distribution
    if re.search(r"distribution|histogram|spread|distributed", q) and mentioned:
        target = (numeric_m or mentioned)[0]
        intent = "distribution" if target.kind == "numeric" else "value_counts"
        return AnalysisPlan(intent=intent, column=target.name, conditions=value_conds, chart=chart or ChartRequest(required=True, type="histogram" if intent == "distribution" else "bar"))

    # --- percentage of rows matching something
    if re.search(r"percent|percentage|proportion|share of|fraction|ratio", q):
        if conditions:
            return AnalysisPlan(intent="percentage", conditions=conditions)
        if low_card:
            return AnalysisPlan(intent="value_counts", column=low_card[0].name, chart=chart)
        return AnalysisPlan(intent="clarification", message="Which group should I calculate the percentage for? For example: 'What percentage of students are from CSE?'")

    # --- unique / distinct / list all values
    if re.search(r"\b(unique|distinct)\b", q) and mentioned:
        if re.search(r"\bhow many\b|\bnumber of\b|\bcount\b", q):
            return AnalysisPlan(intent="aggregation", operation="nunique", column=mentioned[0].name)
        return AnalysisPlan(intent="unique_values", column=mentioned[0].name)
    if cat_m and not numeric_m and re.search(r"\b(list|what are|show)\b.*\b(all|the|different)\b|\blist\b", q) and not re.search(r"\b(by|per|each)\b", q):
        return AnalysisPlan(intent="unique_values", column=cat_m[0].name)

    # --- group by a date column
    date_col = date_m[0] if date_m else (only_date if grain_m else None)
    if date_col and (grain_m or re.search(r"\b(over time|trend|by|per)\b", q)) and not date_conds:
        grain = "month"
        if grain_m:
            word = grain_m.group(1)
            grain = "year" if word.startswith("year") else "day" if word in ("day", "daily") else "weekday" if "week" in word else "month"
        target = numeric_m[0] if numeric_m else None
        agg = (op_all or "sum") if target else "count"
        return AnalysisPlan(
            intent="groupby_aggregation", group_by=date_col.name, date_grain=grain,
            target_column=target.name if target else None, operation=agg, conditions=value_conds, chart=chart,
        )

    # --- group by one or two categories
    by_cue = bool(re.search(r"\b(by|per|each|across|for each|which|grouped)\b", q))
    if low_card and (numeric_m or by_cue or desc or asc or (pivot_word and len(low_card) > 1)):
        group = low_card[0]
        group2 = low_card[1] if len(low_card) > 1 and (re.search(r"\b(by|per|each)\b", q) or pivot_word) else None
        target = numeric_m[0] if numeric_m else None
        limit = n
        if limit is None and (desc or asc) and not re.search(r"\b(by|per|each)\b", q):
            limit = 1
        agg = op_all if (target and by_cue and op_all) else (op or ("mean" if target else "count"))
        if target is None and (desc or asc) and not re.search(r"\b(most|least|fewest|how many|number|count|popular|common|sold)\b", q):
            options = ", ".join(c for c in profile.numeric_columns if c not in ids)
            return AnalysisPlan(
                intent="clarification",
                message=f"Which metric should I compare {group.name} on? Try naming a numeric column, e.g. 'highest average X by {group.name}'. Numeric columns: {options}.",
            )
        if target is None and not group2 and not (desc or asc) and not re.search(r"\b(how many|count|number)\b", q) and by_cue and not re.search(r"\bwhich\b", q):
            return AnalysisPlan(intent="value_counts", column=group.name, conditions=value_conds, chart=chart)
        remaining = [c for c in conditions if c.column not in (group.name, group2.name if group2 else None) or not by_cue]
        return AnalysisPlan(
            intent="groupby_aggregation", group_by=group.name, group_by_2=group2.name if group2 else None,
            target_column=target.name if target else None, operation=agg,
            order="asc" if asc and not desc else "desc", limit=limit, conditions=remaining, chart=chart,
            pivot=True if (pivot_word and group2) else None,
        )

    # --- "who ..." / "which student ..." with a ranking word: return the matching row
    rank = re.search(r"\b(top|bottom|first|last|best|worst|rank|ranking|ranked)\b", q) or (n and (desc or asc))
    if numeric_m and (desc or asc) and re.match(r"(who|which \w+|what \w+ (has|have|is|are))\b", q):
        return AnalysisPlan(intent="bottom_n" if asc and not desc else "top_n", column=numeric_m[0].name, limit=n or 1, conditions=conditions)
    if (desc or asc) and not numeric_m and conditions and not re.search(r"\b(how many|count|number)\b", q):
        options = ", ".join(c for c in profile.numeric_columns if c not in ids)
        return AnalysisPlan(intent="clarification", message=f"Which column should I rank by? Numeric columns: {options}.")

    # --- preview / row listing without a ranking column
    if re.search(r"\b(preview|sample|head)\b", q) or (rank and not numeric_m) or re.search(r"\bshow (me )?(the )?(all )?(data|dataset|rows|records)\b", q):
        return AnalysisPlan(intent="filter", limit=n or 10, conditions=conditions, chart=chart)

    # --- top / bottom N rows by a numeric column
    if numeric_m and rank:
        bottom = bool(re.search(r"\b(bottom|worst|lowest|last)\b", q)) and not re.search(r"\b(top|best|highest)\b", q)
        return AnalysisPlan(intent="bottom_n" if bottom else "top_n", column=numeric_m[0].name, limit=n or 10, conditions=conditions, chart=chart)

    # --- counting rows
    if re.search(r"\b(how many|number of|count)\b", q):
        if cat_m and not conditions and not value_conds:
            return AnalysisPlan(intent="aggregation", operation="nunique", column=cat_m[0].name)
        if not numeric_m or num_conds:
            return AnalysisPlan(intent="aggregation", operation="count", conditions=conditions) if conditions else AnalysisPlan(intent="row_count")
    if re.search(r"\b(rows|records|entries)\b", q) and re.search(r"\b(how many|total|number)\b", q):
        return AnalysisPlan(intent="row_count")

    # --- single statistic
    if numeric_m and (op or desc or asc) and not (num_conds and not op and not (desc or asc)):
        agg = op or ("max" if desc else "min")
        return AnalysisPlan(intent="aggregation", operation=agg, column=numeric_m[0].name, conditions=conditions, chart=chart)
    if op and not mentioned:
        m = re.search(r"\b(?:average|avg|mean|median|sum|total|maximum|minimum|max|min)\s+(?:of\s+)?(?:the\s+)?([a-z_]+)", q)
        token = m.group(1) if m else None
        if token and token not in STOP_TOKENS and token not in ROW_NOUNS:
            return AnalysisPlan(intent="aggregation", operation=op, column=token, conditions=conditions)

    # --- filtering
    if conditions:
        return AnalysisPlan(intent="filter", conditions=conditions, chart=chart)

    # --- bare column mention
    if mentioned:
        target = mentioned[0]
        if target.kind == "numeric":
            return AnalysisPlan(intent="describe", column=target.name)
        return AnalysisPlan(intent="value_counts", column=target.name, chart=chart)
    if re.search(r"\b(summary|describe|overview|statistics|stats)\b", q):
        return AnalysisPlan(intent="describe")
    numeric_example = next((c for c in profile.numeric_columns if c not in ids), "value")
    cat_example = profile.categorical_columns[0] if profile.categorical_columns else "category"
    return AnalysisPlan(
        intent="clarification",
        message=f"I wasn't sure what to calculate. Try mentioning a column and an operation, e.g. 'average {numeric_example} by {cat_example}'.",
    )

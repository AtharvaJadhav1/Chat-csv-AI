"""OR logic, negation, text filters, percentiles, top-percent, rank, outliers and pivot tables."""
import pandas as pd
import pytest

from .conftest import SAMPLE

DF = pd.read_csv(SAMPLE)


def test_or_between_different_columns(ask):
    res = ask("students with marks above 90 or attendance below 60")
    assert res["analysis"]["plan"]["condition_logic"] == "or"
    assert res["table"]["total_rows"] == int(((DF.marks > 90) | (DF.attendance < 60)).sum())


def test_two_values_of_same_column_stay_and_with_other_filter(ask):
    res = ask("students from Pune or Mumbai with marks above 90")
    assert res["analysis"]["plan"]["condition_logic"] == "and"
    assert res["table"]["total_rows"] == int((DF.city.isin(["Pune", "Mumbai"]) & (DF.marks > 90)).sum())


def test_negation(ask):
    assert ask("show students not from CSE")["table"]["total_rows"] == int((DF.department != "CSE").sum())
    res = ask("students not in CSE or ECE")
    assert res["table"]["total_rows"] == int((~DF.department.isin(["CSE", "ECE"])).sum())


def test_starts_and_ends_with(ask):
    assert ask("show students whose name starts with A")["table"]["total_rows"] == int(DF.name.str.lower().str.startswith("a").sum())
    assert ask("names ending with a")["table"]["total_rows"] == int(DF.name.str.lower().str.endswith("a").sum())


def test_percentile_and_quartile(ask):
    res = ask("what is the 90th percentile of marks")
    assert float(res["stat"]["value"]) == pytest.approx(DF.marks.quantile(0.9), abs=0.01)
    assert float(ask("first quartile of marks")["stat"]["value"]) == pytest.approx(DF.marks.quantile(0.25), abs=0.01)


def test_percentile_by_group(ask):
    res = ask("75th percentile of attendance by department")
    expected = DF.groupby("department")["attendance"].quantile(0.75).round(2).to_dict()
    assert dict(res["table"]["rows"]) == pytest.approx(expected)


def test_top_and_bottom_percent(ask):
    top = ask("top 10% of students by marks")
    assert top["table"]["total_rows"] == 10
    idx = top["table"]["columns"].index("marks")
    assert min(r[idx] for r in top["table"]["rows"]) >= DF.marks.nlargest(10).min()
    assert ask("bottom 5% by attendance")["table"]["total_rows"] == 5


def test_rank_of_a_named_row(ask):
    res = ask("rank of Kavya Bose by marks")
    assert res["analysis"]["intent"] == "rank"
    row = dict(zip(res["table"]["columns"], res["table"]["rows"][0]))
    expected = int((DF.marks > DF[DF.name == "Kavya Bose"].marks.iloc[0]).sum()) + 1
    assert row["rank"] == expected and row["of"] == int(DF.marks.notna().sum())


def test_rank_needs_a_row(client, students, use_llm):
    use_llm({"intent": "rank", "column": "marks"})
    res = client.post("/api/chat", json={"dataset_id": students, "question": "rank"}).json()
    assert res["status"] == "clarification"


def test_outlier_rows_use_the_iqr_rule(ask, client):
    from .conftest import upload_bytes
    csv = "id,value\n" + "\n".join(f"{i},{10 + i % 5}" for i in range(40)) + "\n99,500\n"
    ds = upload_bytes(client, csv.encode(), "o.csv").json()["dataset_id"]
    res = client.post("/api/chat", json={"dataset_id": ds, "question": "show outliers in value"}).json()
    assert res["table"]["total_rows"] == 1 and res["table"]["rows"][0][1] == 500
    summary = client.post("/api/chat", json={"dataset_id": ds, "question": "are there any outliers"}).json()
    assert summary["stat"]["value"] == "1"


def test_no_outliers_message(ask):
    res = ask("show outliers in marks")
    assert res["status"] == "ok" and "No outliers" in res["answer"]


def test_pivot_table_and_crosstab(ask):
    res = ask("average marks by department and gender")
    assert res["table"]["columns"] == ["department", "Female", "Male"] or set(res["table"]["columns"]) == {"department", "Female", "Male"}
    assert set(res["chart"]["series"]) == {"Female", "Male"}
    cross = ask("crosstab of department and gender")
    assert cross["analysis"]["plan"]["pivot"] is True and cross["table"]["total_rows"] == DF.department.nunique()


def test_date_between_condition_via_llm(client, use_llm):
    from .conftest import upload_bytes
    ds = upload_bytes(client, b"d,v\n2024-01-01,1\n2024-02-01,2\n2024-03-01,3\n", "dates.csv").json()["dataset_id"]
    use_llm({"intent": "filter", "conditions": [{"column": "d", "operator": "between", "value": ["2024-01-15", "2024-03-01"]}]})
    res = client.post("/api/chat", json={"dataset_id": ds, "question": "x"}).json()
    assert res["table"]["total_rows"] == 2


def test_between_needs_two_values(client, students, use_llm):
    use_llm({"intent": "filter", "conditions": [{"column": "marks", "operator": "between", "value": 5}]})
    assert client.post("/api/chat", json={"dataset_id": students, "question": "x"}).json()["status"] == "error"


def test_percentile_requires_a_value(client, students, use_llm):
    use_llm({"intent": "aggregation", "operation": "percentile", "column": "marks"})
    assert client.post("/api/chat", json={"dataset_id": students, "question": "x"}).json()["status"] == "clarification"

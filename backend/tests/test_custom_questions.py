"""Custom questions on a second dataset (sales.csv) to prove nothing is tied to students.csv."""
from pathlib import Path

import pandas as pd
import pytest

from .conftest import upload_bytes

SALES = Path(__file__).resolve().parents[2] / "sample_data" / "sales.csv"
DF = pd.read_csv(SALES)


@pytest.fixture
def sales(client):
    return upload_bytes(client, SALES.read_bytes(), "sales.csv").json()["dataset_id"]


@pytest.fixture
def ask_s(client, sales):
    return lambda q: client.post("/api/chat", json={"dataset_id": sales, "question": q}).json()


def test_underscore_column_names_are_understood(ask_s):
    res = ask_s("show orders with discount_pct above 10")
    assert res["table"]["total_rows"] == int((DF["discount_pct"] > 10).sum())


def test_total_amount_column_is_not_mistaken_for_a_sum(ask_s):
    res = ask_s("show me orders from West where total amount is over 50000")
    assert res["analysis"]["intent"] == "filter"
    assert res["table"]["total_rows"] == int(((DF["region"] == "West") & (DF["total_amount"] > 50000)).sum())


def test_total_by_group_is_a_sum(ask_s):
    res = ask_s("total amount by region")
    assert dict(res["table"]["rows"]) == DF.groupby("region")["total_amount"].sum().to_dict()


def test_date_range_filter(ask_s):
    res = ask_s("show orders between 2024-03-01 and 2024-03-31")
    expected = DF[(DF["order_date"] >= "2024-03-01") & (DF["order_date"] <= "2024-03-31")]
    assert res["table"]["total_rows"] == len(expected)


def test_synonym_metric_and_trend(ask_s):
    res = ask_s("Show monthly sales trend")
    assert res["chart"]["type"] == "line" and "total_amount" in res["answer"]


def test_two_column_grouping_is_a_pivot_table(ask_s):
    res = ask_s("total amount by category and region")
    assert res["table"]["columns"][0] == "category" and set(res["table"]["columns"][1:]) == set(DF["region"].unique())
    assert res["table"]["total_rows"] == DF["category"].nunique()
    assert set(res["chart"]["series"]) == set(DF["region"].unique())
    row = next(r for r in res["table"]["rows"] if r[0] == "Electronics")
    cell = row[res["table"]["columns"].index("North")]
    assert cell == pytest.approx(DF[(DF.category == "Electronics") & (DF.region == "North")]["total_amount"].sum())


def test_long_form_when_pivot_is_disabled(client, sales):
    from app.api.deps import get_planner
    from app.main import app
    from app.services.planner import LLMPlanner
    from .conftest import FakeLLM
    plan = {"intent": "groupby_aggregation", "group_by": "category", "group_by_2": "region", "target_column": "total_amount", "operation": "sum", "pivot": False}
    app.dependency_overrides[get_planner] = lambda: LLMPlanner(FakeLLM(plan))
    res = client.post("/api/chat", json={"dataset_id": sales, "question": "x"}).json()
    assert res["table"]["total_rows"] == DF.groupby(["category", "region"]).ngroups and res["chart"]["xAxis"] == "group"


def test_compare_named_groups(ask_s):
    res = ask_s("compare average total amount between North and South")
    assert {r[0] for r in res["table"]["rows"]} == {"North", "South"}


def test_plural_category_listing(ask_s):
    assert ask_s("list all categories")["analysis"]["intent"] == "unique_values"


def test_who_questions_return_the_row(ask_s):
    res = ask_s("who gave the highest rating")
    assert res["status"] in ("ok", "clarification")
    res = ask_s("What is the highest total amount?")
    assert res["stat"]["value"] == f"{DF['total_amount'].max():,}"


def test_ambiguous_ranking_asks_for_clarification(client, students):
    res = client.post("/api/chat", json={"dataset_id": students, "question": "best student in CSE"}).json()
    assert res["status"] == "clarification" and "marks" in res["answer"]

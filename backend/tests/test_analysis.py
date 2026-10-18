import pandas as pd
import pytest

from .conftest import SAMPLE

DF = pd.read_csv(SAMPLE)


def test_row_count(ask):
    res = ask("How many students are there?")
    assert res["status"] == "ok" and res["stat"]["value"] == "100"
    assert res["analysis"]["intent"] == "row_count"


def test_average(ask):
    res = ask("What is the average marks?")
    assert res["analysis"]["operation"] == "mean"
    assert res["stat"]["value"] == f"{DF['marks'].mean():.2f}"


def test_median_attendance(ask):
    res = ask("What is the median attendance?")
    assert float(res["stat"]["value"]) == pytest.approx(DF["attendance"].median())


def test_groupby_with_table_and_chart(ask):
    res = ask("What is the average marks by department?")
    expected = DF.groupby("department")["marks"].mean().round(2)
    table = dict(res["table"]["rows"])
    assert table == pytest.approx(expected.to_dict())
    assert res["chart"]["type"] == "bar" and res["chart"]["xAxis"] == "department"
    assert "Grouped the dataset by department" in res["analysis"]["explanation"]


def test_highest_group(ask):
    res = ask("Which department has the highest average marks?")
    expected = DF.groupby("department")["marks"].mean().idxmax()
    assert res["answer"].startswith(expected)
    assert res["analysis"]["plan"]["limit"] == 1


def test_filter(ask):
    res = ask("Find students with marks above 90")
    assert res["table"]["total_rows"] == int((DF["marks"] > 90).sum())
    marks_idx = res["table"]["columns"].index("marks")
    assert all(row[marks_idx] > 90 for row in res["table"]["rows"])


def test_attendance_below_75_percent(ask):
    res = ask("Show students with attendance below 75%")
    assert res["table"]["total_rows"] == int((DF["attendance"] < 75).sum())


def test_filter_by_category_value(ask):
    res = ask("Show students from Mechanical with marks above 70")
    assert res["status"] == "ok"
    dept = res["table"]["columns"].index("department")
    assert {row[dept] for row in res["table"]["rows"]} == {"Mechanical"}


def test_top_n_sorted_descending(ask):
    res = ask("Show the top 10 students by marks")
    idx = res["table"]["columns"].index("marks")
    marks = [row[idx] for row in res["table"]["rows"]]
    assert len(marks) == 10 and marks == sorted(marks, reverse=True)
    assert marks[0] == DF["marks"].max()


def test_bottom_n(ask):
    res = ask("Show the lowest 5 students by marks")
    idx = res["table"]["columns"].index("marks")
    marks = [row[idx] for row in res["table"]["rows"]]
    assert marks == sorted(DF["marks"].dropna())[:5]


def test_percentage(ask):
    res = ask("What percentage of students are from CSE?")
    assert res["stat"]["value"] == f"{100 * (DF['department'] == 'CSE').mean():.2f}%"


def test_most_common_city(ask):
    res = ask("Which city has the most students?")
    assert res["answer"].startswith(DF["city"].value_counts().idxmax())


def test_missing_values(ask):
    res = ask("Are there any missing values?")
    assert "7" in res["answer"] and res["table"]["total_rows"] == 2


def test_distribution_histogram(ask):
    res = ask("Show the distribution of marks")
    assert res["chart"]["type"] == "histogram"
    assert sum(r["count"] for r in res["chart"]["data"]) == int(DF["marks"].notna().sum())


def test_correlation_scatter(ask):
    for q in ("What is the correlation between marks and attendance?", "Is there a relationship between attendance and marks?"):
        res = ask(q)
        assert res["chart"]["type"] == "scatter"
        r = DF["marks"].corr(DF["attendance"])
        assert res["stat"]["value"] == f"{r:.2f}"


def test_explicit_bar_chart_request(ask):
    res = ask("Show a bar chart of average marks by department")
    assert res["chart"]["type"] == "bar" and len(res["chart"]["data"]) == DF["department"].nunique()


def test_no_chart_for_plain_statistic(ask):
    assert ask("What is the average marks?")["chart"] is None


def test_empty_result(ask):
    res = ask("Show students with marks above 1000")
    assert res["status"] == "ok" and "No rows match" in res["answer"] and res["table"] is None


def test_unknown_column_lists_available(ask):
    res = ask("What's the average salary?")
    assert res["status"] == "error"
    assert "couldn't find a 'salary' column" in res["answer"]
    assert "- marks" in res["answer"] and "- attendance" in res["answer"]


def test_wrong_type_is_explained(client, students):
    from app.api.deps import get_planner
    from app.main import app
    from app.services.planner import LLMPlanner
    from .conftest import FakeLLM
    app.dependency_overrides[get_planner] = lambda: LLMPlanner(FakeLLM({"intent": "aggregation", "operation": "mean", "column": "department"}))
    res = client.post("/api/chat", json={"dataset_id": students, "question": "average department"}).json()
    assert res["status"] == "error" and "categorical" in res["answer"] and "- marks" in res["answer"]


@pytest.mark.parametrize("q", ["What is the weather in Pune?", "Who is the president of India?"])
def test_unsupported_questions(ask, q):
    res = ask(q)
    assert res["status"] == "unsupported"
    assert "can't answer that from the uploaded dataset" in res["answer"]


def test_insights_are_computed_from_data(client, students):
    items = client.post(f"/api/dataset/{students}/insights").json()["insights"]
    text = " ".join(i["detail"] for i in items)
    best = DF.groupby("department")["marks"].mean().idxmax()
    assert f"{best} has the highest average marks" in text
    assert "missing" in text.lower() and "correlation" in text


def test_history_is_recorded_and_clearable(client, students, ask):
    ask("What is the average marks?")
    assert len(client.get(f"/api/dataset/{students}/history").json()) == 1
    client.delete(f"/api/dataset/{students}/history")
    assert client.get(f"/api/dataset/{students}/history").json() == []


def test_date_grouping(client):
    from .conftest import upload_bytes
    csv = "order_date,amount\n" + "\n".join(f"2024-0{m}-1{d},{m * 10 + d}" for m in (1, 2, 3) for d in (1, 2)) + "\n"
    ds = upload_bytes(client, csv.encode(), "sales.csv").json()["dataset_id"]
    res = client.post("/api/chat", json={"dataset_id": ds, "question": "Show total amount by month"}).json()
    assert res["status"] == "ok" and res["chart"]["type"] == "line"
    assert [r[0] for r in res["table"]["rows"]] == ["2024-01", "2024-02", "2024-03"]

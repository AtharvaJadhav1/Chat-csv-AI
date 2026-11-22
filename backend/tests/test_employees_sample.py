"""Third sample dataset (employees.csv): dates, a True/False column, missing values."""
from pathlib import Path

import pandas as pd
import pytest

from .conftest import upload_bytes

PATH = Path(__file__).resolve().parents[2] / "sample_data" / "employees.csv"
DF = pd.read_csv(PATH)


@pytest.fixture
def ask_e(client):
    ds = upload_bytes(client, PATH.read_bytes(), "employees.csv").json()["dataset_id"]
    return lambda q: client.post("/api/chat", json={"dataset_id": ds, "question": q}).json()


def test_profile_detects_types_and_gaps(client):
    p = upload_bytes(client, PATH.read_bytes(), "employees.csv").json()["profile"]
    assert p["rows"] == 200 and p["datetime_columns"] == ["join_date"] and p["boolean_columns"] == ["remote"]
    assert p["missing_total"] == 13


def test_boolean_column_counts_true_rows(ask_e):
    assert ask_e("How many employees work remote?")["stat"]["value"] == str(int(DF.remote.sum()))
    assert ask_e("how many employees are not remote")["stat"]["value"] == str(int((~DF.remote).sum()))


def test_boolean_share(ask_e):
    res = ask_e("what percentage of employees work remote")
    assert res["stat"]["value"] == f"{100 * DF.remote.mean():.2f}%"


def test_headcount_by_two_columns_counts_rows(ask_e):
    res = ask_e("Show total headcount by city and department")
    assert res["status"] == "ok" and res["table"]["total_rows"] == DF.city.nunique()
    assert sum(v for row in res["table"]["rows"] for v in row[1:] if v) == 200


def test_salary_by_department_ignores_the_missing_salary(ask_e):
    res = ask_e("average salary by department")
    assert dict(res["table"]["rows"]) == pytest.approx(DF.groupby("department").salary.mean().round(2).to_dict())


def test_missing_values_summary(ask_e):
    res = ask_e("Are there any missing values?")
    assert "13" in res["answer"] and res["table"]["total_rows"] == 3

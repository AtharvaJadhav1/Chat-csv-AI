from app.config import Settings
from app.services.csv_loader import CSVError, load_csv
import pytest

from .conftest import SAMPLE, upload_bytes


def test_upload_valid_csv(client):
    resp = upload_bytes(client, SAMPLE.read_bytes(), "students.csv")
    assert resp.status_code == 200
    body = resp.json()
    profile = body["profile"]
    assert profile["rows"] == 100 and profile["columns"] == 8
    assert {"marks", "attendance", "age"} <= set(profile["numeric_columns"])
    assert {"name", "department", "city"} <= set(profile["categorical_columns"])
    assert len(body["preview"]["rows"]) == 20


def test_profiling_statistics(client):
    profile = upload_bytes(client, SAMPLE.read_bytes(), "students.csv").json()["profile"]
    assert profile["missing_total"] == 7
    cols = {c["name"]: c for c in profile["column_profiles"]}
    assert cols["student_id"]["is_identifier"] is True
    assert cols["marks"]["missing"] == 2
    stats = cols["marks"]["stats"]
    assert stats["min"] <= stats["median"] <= stats["max"] and stats["std"] > 0
    assert cols["department"]["top_values"][0]["count"] >= cols["department"]["top_values"][-1]["count"]


@pytest.mark.parametrize(
    "data,name,status",
    [
        (b"", "empty.csv", 400),
        (b"   \n  ", "blank.csv", 400),
        (b"a,b,c\n", "header_only.csv", 400),
        (b"a,b\n1,2\n3,4,5,6\n", "ragged.csv", 400),
        (b"a,b\n1,2\n", "data.txt", 415),
        (b"\x00\x01\x02\x03binary", "bin.csv", 400),
    ],
)
def test_invalid_csv_rejected(client, data, name, status):
    resp = upload_bytes(client, data, name)
    assert resp.status_code == status
    assert resp.json()["detail"]


def test_duplicate_and_blank_column_names_are_renamed(client):
    resp = upload_bytes(client, b"score,score,\n1,2,3\n4,5,6\n", "dups.csv").json()
    names = [c["name"] for c in resp["profile"]["column_profiles"]]
    assert names == ["score", "score_2", "column_3"]
    assert any("Duplicate" in w for w in resp["warnings"])


def test_encoding_and_delimiter_handling(client):
    data = "name;city\nJosé;Zürich\nAnna;Köln\n".encode("cp1252")
    resp = upload_bytes(client, data, "semi.csv")
    assert resp.status_code == 200
    assert resp.json()["profile"]["columns"] == 2


def test_large_dataset_validation():
    small = Settings(max_rows=5, max_file_size_mb=1)
    rows = "a,b\n" + "\n".join(f"{i},{i}" for i in range(10))
    with pytest.raises(CSVError, match="exceeds the limit of 5 rows"):
        load_csv(rows.encode(), "big.csv", small)
    with pytest.raises(CSVError) as exc:
        load_csv(b"a,b\n" + b"1,2\n" * 400_000, "huge.csv", small)
    assert exc.value.status_code == 413


def test_preview_pagination_search_and_delete(client, students):
    page = client.get(f"/api/dataset/{students}/preview?page=2&page_size=30").json()
    assert page["page"] == 2 and page["total_pages"] == 4 and len(page["rows"]) == 30
    found = client.get(f"/api/dataset/{students}/preview?search=mechanical").json()
    assert 0 < found["total_rows"] < 100
    assert all("Mechanical" in row for row in found["rows"])
    assert client.delete(f"/api/dataset/{students}").json() == {"deleted": True}
    assert client.get(f"/api/dataset/{students}").status_code == 404


def test_unknown_dataset_is_404(client):
    assert client.post("/api/chat", json={"dataset_id": "nope", "question": "hi"}).status_code == 404

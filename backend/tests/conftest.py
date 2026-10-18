import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_planner, get_store
from app.main import app
from app.services.llm_client import LLMError
from app.services.planner import LLMPlanner, RuleBasedPlanner

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "students.csv"


class FakeLLM:
    """Stands in for the LLM: returns scripted responses (or raises) in order."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def complete_json(self, system: str, user: str) -> str:
        self.calls += 1
        item = self.responses[min(self.calls - 1, len(self.responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item if isinstance(item, str) else json.dumps(item)


@pytest.fixture
def client():
    get_store()._items.clear()
    app.dependency_overrides[get_planner] = lambda: RuleBasedPlanner()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def use_llm(client):
    def _use(*responses):
        fake = FakeLLM(*responses)
        app.dependency_overrides[get_planner] = lambda: LLMPlanner(fake)
        return fake
    return _use


def upload_bytes(client, data: bytes, name: str = "data.csv"):
    return client.post("/api/dataset/upload", files={"file": (name, data, "text/csv")})


@pytest.fixture
def students(client):
    resp = upload_bytes(client, SAMPLE.read_bytes(), "students.csv")
    assert resp.status_code == 200, resp.text
    return resp.json()["dataset_id"]


@pytest.fixture
def ask(client, students):
    def _ask(question: str) -> dict:
        resp = client.post("/api/chat", json={"dataset_id": students, "question": question})
        assert resp.status_code == 200, resp.text
        return resp.json()
    return _ask


__all__ = ["LLMError"]

"""Planners turn a natural-language question into a structured AnalysisPlan (never code)."""
import json
import logging
import re
import threading
from typing import Any, Protocol

from pydantic import ValidationError

from ..config import Settings
from ..models.dataset import DatasetRecord
from ..schemas.plan import AnalysisPlan
from ..security.plan_guard import guard_raw_plan
from .heuristic_planner import plan_question
from .llm_client import LLMClient, LLMError, OpenAICompatibleClient
from .prompts import SYSTEM_PROMPT, build_user_prompt


class PlanParseError(Exception):
    """The planner output was not valid JSON or did not match the plan schema."""


def extract_json(text: str) -> Any:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    raise PlanParseError("The AI response was not valid JSON.")


def parse_plan(text: str) -> AnalysisPlan:
    """Untrusted text -> guarded dict -> schema-validated plan. Raises PlanSecurityError / PlanParseError."""
    raw = extract_json(text)
    if not isinstance(raw, dict):
        raise PlanParseError("The AI response was not a JSON object.")
    guard_raw_plan(raw)
    try:
        return AnalysisPlan.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "plan"
        raise PlanParseError(f"The AI plan was invalid at '{where}': {first['msg']}")


class Planner(Protocol):
    name: str

    def plan(self, question: str, record: DatasetRecord) -> AnalysisPlan: ...


class LLMPlanner:
    name = "llm"

    def __init__(self, client: LLMClient):
        self.client = client

    def plan(self, question: str, record: DatasetRecord) -> AnalysisPlan:
        prompt = build_user_prompt(question, record)
        text = self.client.complete_json(SYSTEM_PROMPT, prompt)
        try:
            return parse_plan(text)
        except PlanParseError as exc:
            retry = f"{prompt}\n\nYour previous output was rejected: {exc} Return ONE valid JSON plan object only."
            return parse_plan(self.client.complete_json(SYSTEM_PROMPT, retry))


class RuleBasedPlanner:
    name = "rules"

    def plan(self, question: str, record: DatasetRecord) -> AnalysisPlan:
        return plan_question(question, record)


class FallbackPlanner:
    """Uses the LLM, but degrades to the rule-based planner if the LLM service fails (bad key, timeout, outage)."""

    def __init__(self, primary: Planner, fallback: Planner):
        self.primary, self.fallback = primary, fallback
        self._local = threading.local()

    @property
    def name(self) -> str:
        return getattr(self._local, "name", self.primary.name)

    def plan(self, question: str, record: DatasetRecord) -> AnalysisPlan:
        try:
            plan = self.primary.plan(question, record)
            self._local.name = self.primary.name
            return plan
        except LLMError as exc:
            logging.getLogger("chatcsv.planner").warning("LLM unavailable, using rule-based planner: %s", exc)
            self._local.name = "rules-fallback"
            return self.fallback.plan(question, record)


def build_planner(settings: Settings) -> Planner:
    if settings.llm_enabled:
        return FallbackPlanner(LLMPlanner(OpenAICompatibleClient(settings)), RuleBasedPlanner())
    return RuleBasedPlanner()


__all__ = ["Planner", "FallbackPlanner", "LLMPlanner", "RuleBasedPlanner", "PlanParseError", "LLMError", "build_planner", "parse_plan"]

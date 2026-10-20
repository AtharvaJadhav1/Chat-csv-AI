"""Orchestrates the full pipeline: question -> plan -> validate -> execute -> validate result."""
import logging
import time
from typing import Iterator

from ..models.dataset import DatasetRecord, DatasetStore
from ..schemas.api import AnalysisInfo, ChatResponse, HistoryItem, UsageInfo
from ..schemas.plan import AnalysisPlan
from ..security.plan_guard import PlanSecurityError, guard_question
from ..security.plan_validator import PlanError, validate_plan_with_notes
from .executor import execute_plan
from .llm_client import LLMError
from .planner import PlanParseError, Planner
from .result_validator import validate_result

logger = logging.getLogger("chatcsv.chat")


def _analysis_info(plan: AnalysisPlan, explanation: str) -> AnalysisInfo:
    dumped = plan.model_dump(mode="json", exclude_none=True)
    dumped = {k: v for k, v in dumped.items() if v not in ([], {})}
    return AnalysisInfo(
        intent=plan.intent,
        operation=plan.operation,
        column=plan.target_column or plan.column or plan.group_by,
        explanation=explanation,
        plan=dumped,
    )


def answer_stream(
    record: DatasetRecord, question: str, planner: Planner, store: DatasetStore
) -> Iterator[tuple[str, object]]:
    """Runs the pipeline, yielding ("stage", name) as each real step begins and ("result", ChatResponse) at the end."""
    question = question.strip()
    started = time.perf_counter()
    marks: dict[str, float] = {}
    getattr(planner, "reset_usage", lambda: None)()
    yield "stage", "analyzing"
    try:
        guard_question(question)
        yield "stage", "understanding"
        raw_plan = planner.plan(question, record)
        marks["planned"] = time.perf_counter()
        yield "stage", "running"
        plan, notes = validate_plan_with_notes(raw_plan, record.profile)
        executed = execute_plan(record.df, plan, record.profile)
        yield "stage", "preparing"
        result = validate_result(executed)
        response = ChatResponse(
            status="ok", answer=result.answer, analysis=_analysis_info(plan, result.explanation),
            stat=result.stat, table=result.table, chart=result.chart, planner=planner.name,
            safety="validated", notes=notes,
        )
    except PlanSecurityError as exc:
        logger.warning("blocked unsafe input for dataset %s", record.id)
        response = ChatResponse(status="error", answer=str(exc), planner=planner.name, safety="blocked")
    except LLMError as exc:
        logger.warning("LLM failure: %s", exc)
        response = ChatResponse(status="error", answer=str(exc), planner=planner.name)
    except PlanParseError as exc:
        logger.warning("invalid plan from planner: %s", exc)
        response = ChatResponse(
            status="error",
            answer=f"I couldn't turn that into a valid analysis plan ({exc}). Try rephrasing your question.",
            planner=planner.name,
        )
    except PlanError as exc:
        response = ChatResponse(status=exc.status, answer=exc.message, planner=planner.name)  # type: ignore[arg-type]
    except Exception:
        logger.exception("unexpected error while answering a question")
        response = ChatResponse(
            status="error", answer="Something went wrong while running that analysis. Please try a different question.",
            planner=planner.name,
        )

    finished = time.perf_counter()
    planned = marks.get("planned", finished)
    tokens = getattr(planner, "usage", lambda: None)() or {}
    response.usage = UsageInfo(
        latency_ms=round((finished - started) * 1000),
        plan_ms=round((planned - started) * 1000),
        execute_ms=round((finished - planned) * 1000),
        llm_calls=tokens.get("llm_calls", 0),
        prompt_tokens=tokens.get("prompt_tokens", 0),
        completion_tokens=tokens.get("completion_tokens", 0),
        total_tokens=tokens.get("total_tokens", 0),
    )
    store.add_history(record, HistoryItem(
        question=question, answer=response.answer, intent=response.analysis.intent if response.analysis else None,
        timestamp=response.timestamp,
    ))
    yield "result", response


def answer_question(record: DatasetRecord, question: str, planner: Planner, store: DatasetStore) -> ChatResponse:
    response: ChatResponse | None = None
    for kind, payload in answer_stream(record, question, planner, store):
        if kind == "result":
            response = payload  # type: ignore[assignment]
    assert response is not None
    return response

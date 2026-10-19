import json
import logging

from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from ..config import Settings
from ..schemas.api import (
    ChatRequest, ChatResponse, DatasetProfile, HistoryItem, InsightsResponse, PreviewResponse, UploadResponse,
)
from ..services.chat_service import answer_question, answer_stream
from ..services.csv_loader import CSVError, load_csv
from ..services.executor import df_to_table
from ..services.insights import generate_insights
from ..services.planner import Planner
from ..services.profiler import profile_dataframe
from .deps import get_planner, get_record, get_store, settings_dep

logger = logging.getLogger("chatcsv.api")
router = APIRouter(prefix="/api")


def build_preview(record, page: int, page_size: int, search: str | None) -> PreviewResponse:
    df = record.df
    if search and search.strip():
        needle = search.strip().lower()
        mask = df.astype(str).apply(lambda col: col.str.lower().str.contains(needle, regex=False, na=False)).any(axis=1)
        df = df[mask]
    total = len(df)
    pages = max((total + page_size - 1) // page_size, 1)
    page = min(max(page, 1), pages)
    chunk = df.iloc[(page - 1) * page_size: page * page_size]
    table = df_to_table(chunk, max_rows=page_size)
    return PreviewResponse(
        columns=table.columns,
        kinds={c.name: c.kind for c in record.profile.column_profiles},
        rows=table.rows, page=page, page_size=page_size, total_rows=total, total_pages=pages,
    )


@router.get("/health")
def health(settings: Settings = Depends(settings_dep), planner: Planner = Depends(get_planner)):
    return {
        "status": "ok",
        "planner": getattr(planner, "configured_name", planner.name),
        "llm_model": settings.llm_model if getattr(planner, "configured_name", planner.name) == "llm" else None,
        "max_file_size_mb": settings.max_file_size_mb,
        "max_rows": settings.max_rows,
    }


@router.post("/dataset/upload", response_model=UploadResponse)
def upload_dataset(file: UploadFile = File(...), settings: Settings = Depends(settings_dep)):
    raw = file.file.read(settings.max_file_size_bytes + 1)
    try:
        df, warnings = load_csv(raw, file.filename or "", settings)
    except CSVError as exc:
        raise HTTPException(exc.status_code, exc.message)
    profile = profile_dataframe(df, file.filename or "dataset.csv")
    record = get_store().add(profile.filename, df, profile)
    logger.info("dataset %s uploaded: %d rows x %d cols", record.id, profile.rows, profile.columns)
    return UploadResponse(dataset_id=record.id, profile=profile, preview=build_preview(record, 1, 20, None), warnings=warnings)


@router.get("/dataset/{dataset_id}", response_model=DatasetProfile)
def get_dataset(dataset_id: str):
    return get_record(dataset_id).profile


@router.get("/dataset/{dataset_id}/preview", response_model=PreviewResponse)
def preview_dataset(
    dataset_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
):
    return build_preview(get_record(dataset_id), page, page_size, search)


@router.post("/dataset/{dataset_id}/insights", response_model=InsightsResponse)
def dataset_insights(dataset_id: str):
    return InsightsResponse(insights=generate_insights(get_record(dataset_id)))


@router.delete("/dataset/{dataset_id}")
def delete_dataset(dataset_id: str):
    if not get_store().delete(dataset_id):
        raise HTTPException(404, "Dataset not found.")
    return {"deleted": True}


@router.get("/dataset/{dataset_id}/history", response_model=list[HistoryItem])
def get_history(dataset_id: str):
    return get_record(dataset_id).history


@router.delete("/dataset/{dataset_id}/history")
def clear_history(dataset_id: str):
    get_record(dataset_id).history.clear()
    return {"cleared": True}


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, planner: Planner = Depends(get_planner)):
    record = get_record(req.dataset_id)
    return answer_question(record, req.question, planner, get_store())


@router.post("/chat/stream")
def chat_stream(req: ChatRequest, planner: Planner = Depends(get_planner)):
    """Same as /chat but streams newline-delimited JSON: real pipeline stages, then the final result."""
    record = get_record(req.dataset_id)
    store = get_store()

    def events():
        for kind, payload in answer_stream(record, req.question, planner, store):
            body = {"stage": payload} if kind == "stage" else {"result": json.loads(payload.model_dump_json())}
            yield json.dumps(body) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")

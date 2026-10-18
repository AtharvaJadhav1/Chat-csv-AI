from functools import lru_cache

from fastapi import HTTPException

from ..config import Settings, get_settings
from ..models.dataset import DatasetRecord, DatasetStore
from ..services.planner import Planner, build_planner


@lru_cache
def get_store() -> DatasetStore:
    return DatasetStore(get_settings().dataset_ttl_minutes)


@lru_cache
def get_planner() -> Planner:
    return build_planner(get_settings())


def get_record(dataset_id: str) -> DatasetRecord:
    record = get_store().get(dataset_id)
    if record is None:
        raise HTTPException(404, "Dataset not found. It may have expired or been deleted - please upload it again.")
    return record


def settings_dep() -> Settings:
    return get_settings()

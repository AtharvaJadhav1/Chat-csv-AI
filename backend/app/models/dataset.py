"""In-memory dataset store. Uploaded data is never written to disk and expires after a TTL."""
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pandas as pd

from ..schemas.api import DatasetProfile, HistoryItem

MAX_HISTORY = 50


@dataclass
class DatasetRecord:
    id: str
    filename: str
    df: pd.DataFrame
    profile: DatasetProfile
    created_at: datetime
    last_access: datetime
    history: list[HistoryItem] = field(default_factory=list)


class DatasetStore:
    def __init__(self, ttl_minutes: int = 120):
        self._items: dict[str, DatasetRecord] = {}
        self._lock = threading.Lock()
        self.ttl = timedelta(minutes=ttl_minutes)

    def add(self, filename: str, df: pd.DataFrame, profile: DatasetProfile) -> DatasetRecord:
        now = datetime.now(timezone.utc)
        record = DatasetRecord(uuid.uuid4().hex, filename, df, profile, now, now)
        with self._lock:
            self._purge_expired(now)
            self._items[record.id] = record
        return record

    def get(self, dataset_id: str) -> DatasetRecord | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge_expired(now)
            record = self._items.get(dataset_id)
            if record:
                record.last_access = now
            return record

    def delete(self, dataset_id: str) -> bool:
        with self._lock:
            return self._items.pop(dataset_id, None) is not None

    def _purge_expired(self, now: datetime) -> None:
        expired = [k for k, v in self._items.items() if now - v.last_access > self.ttl]
        for k in expired:
            del self._items[k]

    def add_history(self, record: DatasetRecord, item: HistoryItem) -> None:
        record.history.append(item)
        del record.history[:-MAX_HISTORY]

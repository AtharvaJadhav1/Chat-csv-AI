"""Scaling curve: load/profile time, memory and typical-question latency at several file sizes.

    cd backend
    PYTHONPATH=. python eval/scale_curve.py
"""
import io
import json
import statistics
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from app.config import Settings  # noqa: E402
from app.models.dataset import DatasetStore  # noqa: E402
from app.services.chat_service import answer_stream  # noqa: E402
from app.services.csv_loader import load_csv  # noqa: E402
from app.services.planner import RuleBasedPlanner  # noqa: E402
from app.services.profiler import profile_dataframe  # noqa: E402
from make_large_dataset import build  # noqa: E402

QUESTIONS = {
    "simple average": "What is the average total amount?",
    "group by category": "average rating by category",
    "group by month": "total amount by month",
    "filter": "show orders from North where total amount is over 5000",
    "top 10": "Show the top 10 orders by total amount",
    "correlation": "What is the correlation between rating and delivery days?",
}
SIZES = [1_000, 10_000, 50_000, 100_000]
settings = Settings(max_rows=1_000_000, max_file_size_mb=200)
proc = psutil.Process()
planner = RuleBasedPlanner()
out = []
for n in SIZES:
    data = build(n)
    buf = io.StringIO()
    data.to_csv(buf, index=False)
    raw = buf.getvalue().encode()
    before = proc.memory_info().rss
    t = time.perf_counter()
    df, _ = load_csv(raw, f"orders_{n}.csv", settings)
    t_load = time.perf_counter() - t
    t = time.perf_counter()
    profile = profile_dataframe(df, f"orders_{n}.csv")
    t_prof = time.perf_counter() - t
    store = DatasetStore()
    record = store.add(f"orders_{n}.csv", df, profile)
    row = {
        "rows": n, "file_mb": round(len(raw) / 1e6, 1), "load_s": round(t_load, 2), "profile_s": round(t_prof, 2),
        "dataframe_mb": round(df.memory_usage(deep=True).sum() / 1e6, 1), "rss_growth_mb": round((proc.memory_info().rss - before) / 1e6),
        "questions_ms": {},
    }
    for label, q in QUESTIONS.items():
        times = []
        for _ in range(5):
            record.history.clear()
            t = time.perf_counter()
            for kind, payload in answer_stream(record, q, planner, store):
                pass
            times.append((time.perf_counter() - t) * 1000)
        row["questions_ms"][label] = round(statistics.median(times))
    out.append(row)
    print(f"{n:>7,} rows | {row['file_mb']:>5} MB file | load {row['load_s']}s + profile {row['profile_s']}s | df {row['dataframe_mb']} MB | " + ", ".join(f"{k} {v} ms" for k, v in row["questions_ms"].items()))
(Path(__file__).parent / "results_scale_curve.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

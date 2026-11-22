"""Scale benchmark: how does ChatCSV AI behave on a large file (default: the 50,000-row orders dataset)?

    cd backend
    python eval/make_large_dataset.py                       # once
    PYTHONPATH=. python eval/scale_benchmark.py --planner rules

Measures: upload/parse/profile time and memory, endpoint latency (upload, preview, insights), per-question
latency (plan vs execute vs total), response size, tokens (LLM mode) and accuracy against pandas ground truth.
"""
import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

import pandas as pd
import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.models.dataset import DatasetStore  # noqa: E402
from app.services.chat_service import answer_stream  # noqa: E402
from app.services.csv_loader import load_csv  # noqa: E402
from app.services.planner import RuleBasedPlanner  # noqa: E402
from app.services.profiler import profile_dataframe  # noqa: E402

PROC = psutil.Process()
rss_mb = lambda: PROC.memory_info().rss / 1e6  # noqa: E731


def num(x) -> float:
    return float(str(x).replace(",", "").replace("%", "").replace("#", ""))


def stat(r):
    return num(r.stat.value) if r.stat else None


def rows(r):
    return r.table.total_rows if r.table else 0


def pairs(r):
    return {str(row[0]): row[1] for row in r.table.rows} if r.table else {}


def col(r, name):
    i = r.table.columns.index(name)
    return [row[i] for row in r.table.rows]


def close(a, b, tol=0.02):
    return a is not None and abs(a - b) <= tol * max(1.0, abs(b))


def dict_close(got, want):
    want = {str(k): float(v) for k, v in (want.to_dict() if hasattr(want, "to_dict") else want).items()}
    return bool(got) and set(got) == set(want) and all(close(float(got[k]), want[k]) for k in want)


def build_cases(G: pd.DataFrame):
    month = G.order_date.str[:7]
    year = G.order_date.str[:4]
    q1, q3 = G.total_amount.quantile(0.25), G.total_amount.quantile(0.75)
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    n_out = int(((G.total_amount < lo) | (G.total_amount > hi)).sum())
    refusal = lambda r: r.status in ("unsupported", "clarification") and r.table is None and r.stat is None  # noqa: E731
    return [
        ("Aggregation", "How many orders are there?", lambda r: stat(r) == len(G)),
        ("Aggregation", "What is the average total amount?", lambda r: close(stat(r), G.total_amount.mean())),
        ("Aggregation", "What is the median delivery days?", lambda r: close(stat(r), G.delivery_days.median())),
        ("Aggregation", "What is the maximum unit price?", lambda r: stat(r) == G.unit_price.max()),
        ("Aggregation", "What is the total revenue?", lambda r: close(stat(r), G.total_amount.sum())),
        ("Group-by", "total amount by region", lambda r: dict_close(pairs(r), G.groupby("region").total_amount.sum())),
        ("Group-by", "average rating by category", lambda r: dict_close(pairs(r), G.groupby("category").rating.mean())),
        ("Group-by", "Which category has the highest average total amount?", lambda r: r.answer.startswith(G.groupby("category").total_amount.mean().idxmax())),
        ("Group-by", "number of orders per payment method", lambda r: dict_close(pairs(r), G.payment_method.value_counts())),
        ("Group-by", "total amount by month", lambda r: rows(r) == 36 and dict_close(pairs(r), G.groupby(month).total_amount.sum())),
        ("Group-by", "total amount by year", lambda r: rows(r) == 3 and dict_close(pairs(r), G.groupby(year).total_amount.sum())),
        ("Filtering", "Show orders with discount_pct above 20", lambda r: rows(r) == int((G.discount_pct > 20).sum())),
        ("Filtering", "show orders from North where total amount is over 5000", lambda r: rows(r) == int(((G.region == "North") & (G.total_amount > 5000)).sum())),
        ("Top-N", "Show the top 10 orders by total amount", lambda r: col(r, "total_amount") == sorted(G.total_amount, reverse=True)[:10]),
        ("Top-N", "top 1% of orders by total amount", lambda r: rows(r) == math.ceil(len(G) * 0.01)),
        ("Stats & charts", "What is the correlation between rating and delivery days?", lambda r: close(stat(r), G.rating.corr(G.delivery_days), 0.01)),
        ("Stats & charts", "What percentage of orders are returned?", lambda r: close(stat(r), 100 * G.returned.mean(), 0.01)),
        ("Stats & charts", "Are there any missing values?", lambda r: f"{int(G.isna().sum().sum()):,}" in r.answer),
        ("Advanced", "average total amount by category and region", lambda r: r.chart is not None and set(r.chart.series or []) == set(G.region.unique()) and rows(r) == G.category.nunique()),
        ("Advanced", "90th percentile of delivery days", lambda r: close(stat(r), G.delivery_days.quantile(0.9), 0.01)),
        ("Advanced", "show outliers in total amount", lambda r: rows(r) == n_out),
        ("Refusal", "What is the weather in Pune?", refusal),
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(ROOT / "sample_data" / "orders_50k.csv"))
    ap.add_argument("--planner", choices=["rules", "llm"], default="rules")
    ap.add_argument("--repeats", type=int, default=5, help="repetitions per question (rules mode)")
    args = ap.parse_args()
    settings = get_settings()
    path = Path(args.file)
    raw = path.read_bytes()
    G = pd.read_csv(path)  # independent ground truth
    summary: dict = {"file": path.name, "file_mb": round(len(raw) / 1e6, 2), "rows": len(G), "columns": G.shape[1], "planner": args.planner}

    # ---- phase 1: load + profile (fresh objects, measured in this process)
    rss0 = rss_mb()
    t = time.perf_counter()
    df, warnings = load_csv(raw, path.name, settings)
    t_load = time.perf_counter() - t
    t = time.perf_counter()
    profile = profile_dataframe(df, path.name)
    t_profile = time.perf_counter() - t
    store = DatasetStore()
    record = store.add(path.name, df, profile)
    summary["load"] = {
        "parse_and_validate_s": round(t_load, 3), "profile_s": round(t_profile, 3), "total_s": round(t_load + t_profile, 3),
        "dataframe_mb": round(df.memory_usage(deep=True).sum() / 1e6, 1), "process_rss_growth_mb": round(rss_mb() - rss0),
        "missing_total": profile.missing_total,
    }
    print(f"loaded {len(df):,} rows in {t_load:.2f}s + profile {t_profile:.2f}s | dataframe {summary['load']['dataframe_mb']} MB | RSS +{summary['load']['process_rss_growth_mb']} MB")

    # ---- phase 2: endpoint latency through the real FastAPI app
    from fastapi.testclient import TestClient

    from app.api.deps import get_planner
    from app.main import app

    app.dependency_overrides[get_planner] = lambda: RuleBasedPlanner()
    client = TestClient(app)
    t = time.perf_counter()
    up = client.post("/api/dataset/upload", files={"file": (path.name, raw, "text/csv")})
    t_upload = time.perf_counter() - t
    ds = up.json()["dataset_id"]
    timings = {"upload_endpoint_s": round(t_upload, 3), "upload_response_kb": round(len(up.content) / 1024, 1)}
    for name, fn in (
        ("preview_page_ms", lambda: client.get(f"/api/dataset/{ds}/preview?page=1&page_size=15")),
        ("preview_search_ms", lambda: client.get(f"/api/dataset/{ds}/preview?page=1&page_size=15&search=north")),
        ("insights_ms", lambda: client.post(f"/api/dataset/{ds}/insights")),
    ):
        t = time.perf_counter()
        resp = fn()
        timings[name] = round((time.perf_counter() - t) * 1000)
        assert resp.status_code == 200, (name, resp.status_code)
    summary["endpoints"] = timings
    print("endpoints:", timings)
    client.delete(f"/api/dataset/{ds}")

    # ---- phase 3: questions
    if args.planner != "rules":
        sys.exit("External LLM calls are disabled. Run with --planner rules.")
    planner = RuleBasedPlanner()
    repeats = args.repeats if args.planner == "rules" else 1
    results = []
    for category, question, check in build_cases(G):
        walls, plans, execs, last = [], [], [], None
        for _ in range(repeats):
            record.history.clear()
            t = time.perf_counter()
            for kind, payload in answer_stream(record, question, planner, store):
                if kind == "result":
                    last = payload
            wall = (time.perf_counter() - t) * 1000
            waited = (planner.usage() or {}).get("waited_ms", 0) if args.planner == "llm" else 0
            walls.append(wall - waited)
            plans.append(max(0, last.usage.plan_ms - waited))
            execs.append(last.usage.execute_ms)
        try:
            passed = bool(check(last))
        except Exception:
            passed = False
        tokens = (planner.usage() or {}) if args.planner == "llm" else {}
        results.append({
            "category": category, "question": question, "passed": passed, "status": last.status,
            "latency_ms": round(statistics.median(walls)), "plan_ms": round(statistics.median(plans)), "execute_ms": round(statistics.median(execs)),
            "response_kb": round(len(last.model_dump_json()) / 1024, 1), "answer": last.answer[:140],
            "prompt_tokens": tokens.get("prompt_tokens", 0), "completion_tokens": tokens.get("completion_tokens", 0),
        })
        print(f"[{'PASS' if passed else 'FAIL'}] {category:15} {question[:58]:58} {results[-1]['latency_ms']:6d} ms  (plan {results[-1]['plan_ms']}, run {results[-1]['execute_ms']})  {results[-1]['response_kb']} KB")

    ok = sum(r["passed"] for r in results)
    lat = sorted(r["latency_ms"] for r in results)
    ran = [r for r in results if r["execute_ms"] > 0 or r["status"] == "ok"]
    summary.update({
        "questions": len(results), "passed": ok, "accuracy": round(100 * ok / len(results), 1),
        "latency_ms": {"median": round(statistics.median(lat)), "p95": lat[min(len(lat) - 1, int(0.95 * len(lat)))], "max": lat[-1]},
        "execute_ms_median": round(statistics.median([r["execute_ms"] for r in ran])), "execute_ms_max": max(r["execute_ms"] for r in results),
        "response_kb_max": max(r["response_kb"] for r in results),
        "tokens": {"prompt_mean": round(statistics.mean([r["prompt_tokens"] for r in results if r["prompt_tokens"]] or [0])),
                   "completion_mean": round(statistics.mean([r["completion_tokens"] for r in results if r["completion_tokens"]] or [0]))},
        "peak_rss_mb": round(rss_mb()),
    })
    out = Path(__file__).parent / f"results_scale_{args.planner}.json"
    out.write_text(json.dumps({"summary": summary, "cases": results}, indent=2), encoding="utf-8")
    print(f"\n{ok}/{len(results)} correct ({summary['accuracy']}%)  median {summary['latency_ms']['median']} ms  max {summary['latency_ms']['max']} ms  peak RSS {summary['peak_rss_mb']} MB -> {out.name}")


if __name__ == "__main__":
    main()

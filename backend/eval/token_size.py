"""Measures how many tokens ChatCSV AI sends to the LLM per question, versus pasting the whole CSV.

    cd backend
    PYTHONPATH=. python eval/token_size.py

Token counts use tiktoken (cl100k_base) when available, otherwise a ~4 characters-per-token estimate.
Llama / Gemini tokenizers differ slightly, so treat every number as an estimate (the provider's own count
is recorded per request by run_eval.py --planner llm).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.models.dataset import DatasetStore  # noqa: E402
from app.services.csv_loader import load_csv  # noqa: E402
from app.services.profiler import profile_dataframe  # noqa: E402
from app.services.prompts import SYSTEM_PROMPT, build_user_prompt  # noqa: E402

try:
    import tiktoken

    _enc = tiktoken.get_encoding("cl100k_base")

    def count(text: str) -> int:
        return len(_enc.encode(text))

    METHOD = "tiktoken cl100k_base"
except Exception:  # offline or not installed

    def count(text: str) -> int:
        return max(1, round(len(text) / 4))

    METHOD = "estimate: 4 characters per token"


def main() -> None:
    settings = get_settings()
    store = DatasetStore()
    out = {"method": METHOD, "system_prompt_chars": len(SYSTEM_PROMPT), "system_prompt_tokens": count(SYSTEM_PROMPT), "datasets": {}}
    question = "What is the average marks by department?"
    for name in ("students", "sales"):
        raw = (ROOT / "sample_data" / f"{name}.csv").read_bytes()
        df, _ = load_csv(raw, f"{name}.csv", settings)
        record = store.add(f"{name}.csv", df, profile_dataframe(df, f"{name}.csv"))
        user = build_user_prompt(question, record)
        csv_text = raw.decode("utf-8")
        per_row = count(csv_text) / len(df)
        out["datasets"][name] = {
            "rows": len(df), "columns": len(df.columns),
            "schema_prompt_tokens": count(user),
            "per_question_input_tokens": count(SYSTEM_PROMPT) + count(user),
            "whole_csv_tokens": count(csv_text),
            "tokens_per_csv_row": round(per_row, 1),
            "whole_csv_tokens_at_100k_rows": round(per_row * 100_000),
        }
    out["typical_output_tokens"] = count(json.dumps({"intent": "groupby_aggregation", "group_by": "department", "operation": "mean", "target_column": "marks", "order": "desc"}))
    Path(__file__).with_name("results_tokens.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

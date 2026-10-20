# ChatCSV AI

> **Talk to your data. Get answers instantly.**

Upload any CSV file and ask questions in plain English. ChatCSV AI turns each question into a **structured, validated analysis plan**, runs it with **allowlisted pandas operations**, and returns a grounded answer, table or chart. This is the solution for **PS 91 - Chat-with-your-CSV Tool**.

![Python](https://img.shields.io/badge/Python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688) ![Next.js](https://img.shields.io/badge/Next.js-14-black) ![pandas](https://img.shields.io/badge/pandas-2.2-150458) ![Tests](https://img.shields.io/badge/tests-91%20passing-brightgreen)

## Quick start

```bash
git clone https://github.com/AtharvaJadhav1/Chat-csv-AI.git
cd Chat-csv-AI
docker compose up --build
```

Open <http://localhost:3000>, click **Try sample students.csv**, and start asking questions. No API key is needed; add `OPENAI_API_KEY` to a `.env` file for free-form LLM understanding.

## Features

- Drag-and-drop CSV upload with progress, size/row limits, encoding and delimiter detection, malformed/empty/duplicate-column handling
- Automatic dataset profiling (types, missing values, unique counts, mean/median/min/max/std, top categories)
- Searchable, paginated preview with column-type indicators
- ChatGPT-style chat with follow-up context, copy, retry, re-run and clear
- 24 analysis types (see below), each returning text, stat card, table and/or chart
- Charts (bar, line, pie, histogram, scatter, area) rendered with Recharts from a backend-provided spec; charts only appear when they help
- "Analyze Dataset" button producing insights computed from the data (leaders, missing data, correlations, outliers, skew)
- Out-of-scope questions are refused instead of hallucinated; unknown columns list the available ones
- Light/dark mode, responsive layout, loading / empty / error states
- Real pipeline-stage progress (streamed from the backend, no fake delays)

## Architecture

```
CSV upload -> validation -> profiling -> in-memory dataset store
                                              |
Question -> [guard] -> Planner (LLM or rules) -> AnalysisPlan (JSON)
          -> schema validation (Pydantic) -> dataset validation (columns/types/values)
          -> executor (allowlisted pandas) -> result validation
          -> answer + table + chart spec -> frontend (Recharts)
```

| Layer | Folder | Responsibility |
|---|---|---|
| API | `backend/app/api` | REST endpoints (FastAPI) |
| Schemas | `backend/app/schemas` | Pydantic models: plan, requests, responses, chart spec |
| Services | `backend/app/services` | CSV loader, profiler, planners, executor, insights, orchestration |
| Security | `backend/app/security` | Input guard + plan validator (no execution happens here) |
| Models | `backend/app/models` | In-memory dataset store with TTL |
| Frontend | `frontend/` | Next.js 14 (App Router), Tailwind, Recharts, Lucide |

Keeping the LLM (`services/planner.py`, `llm_client.py`, `prompts.py`), security validation (`security/`) and data execution (`services/executor.py`) in separate modules means the LLM never touches data and the executor never trusts the LLM.

### Folder structure

```
chatcsv-ai/
├── backend/
│   ├── app/{main.py, config.py, api/, services/, models/, schemas/, utils/, security/}
│   ├── tests/            # 91 pytest tests
│   ├── requirements.txt, pytest.ini, Dockerfile
├── frontend/
│   ├── app/              # pages: / /dataset /chat /insights /history /settings
│   ├── components/, lib/, types/, public/
│   └── package.json, Dockerfile
├── sample_data/students.csv      # 100 synthetic students
├── docker-compose.yml, .env.example, README.md
```

## Setup

Requirements: Python 3.11+, Node 20+.

```bash
cp .env.example .env        # optional: add OPENAI_API_KEY
```

### Run the backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs are served at <http://localhost:8000/docs>.

### Run the frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

### Run with Docker

```bash
docker compose up --build
```

Frontend: <http://localhost:3000>, backend: <http://localhost:8000>. `NEXT_PUBLIC_API_URL` is baked into the frontend image at build time and is the URL the *browser* uses to reach the backend.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | _(empty)_ | Enables the LLM planner. Empty = offline rule-based planner. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible `/chat/completions` endpoint |
| `LLM_MODEL` | `gpt-4o-mini` | Model name sent to the provider |
| `LLM_TIMEOUT_SECONDS` | `30` | LLM request timeout |
| `MAX_FILE_SIZE_MB` | `25` | Upload size limit (HTTP 413 above it) |
| `MAX_ROWS` | `100000` | Row limit; larger files are rejected, never truncated |
| `DATASET_TTL_MINUTES` | `120` | Datasets are deleted from memory after this much inactivity |
| `CORS_ORIGINS` | localhost:3000 | Allowed browser origins |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL used by the frontend |

No API key is ever hardcoded; `.env` is git-ignored.

## AI workflow

1. **Context**: the planner receives the question, the dataset *schema* (column names, types, stats, top category values) and the last few Q&A pairs. Never the full dataset.
2. **Plan**: the LLM must return a single JSON object (`prompts.py` documents the intents, operators and examples). JSON-mode is requested when the provider supports it.
3. **Parse + guard**: the text is parsed, scanned for blocked constructs, and validated with Pydantic (`AnalysisPlan`). Invalid JSON triggers one retry that feeds the error back to the model; after that the user gets a clear error.
4. **Validate against the dataset**: columns are resolved (case/plural tolerant), types are checked (e.g. no `mean` of text), condition values are coerced to the column type.
5. **Execute**: one fixed function per intent builds pandas operations.
6. **Validate result**: shape, size and finite-number checks.
7. **Respond**: answer text is generated *by Python from the computed result* (not by the LLM), so numbers can't be hallucinated. A plain-English explanation of what was done is attached ("How this was calculated").

If no API key is set, a deterministic **rule-based planner** produces the same `AnalysisPlan` format, so the rest of the pipeline is identical and the app works offline (the header shows which planner is active).

### Supported analytics

Row count, column count, column listing, mean, median, min, max, sum, count, std, unique values / distinct counts, value frequency, filtering (`==, !=, >, >=, <, <=, contains, in, not_in, is_null, not_null`), sorting, group-by + aggregation, top N, bottom N, missing-value analysis, Pearson correlation (pair or matrix), distribution (histogram), percentages, descriptive statistics, ranking/comparison (group-by with ordering), date grouping (year/month/day/weekday), date-range filters, **OR / NOT filters** ("marks above 90 or attendance below 60", "not from CSE"), **text filters** (starts with / ends with / contains), **percentiles and quartiles** ("90th percentile of marks", also per group), **top/bottom X%** of rows, **rank lookup** ("rank of Kavya Bose by marks"), **outlier rows** via the 1.5 × IQR rule, and **pivot tables** with grouped charts ("average marks by department and gender", "crosstab of department and gender"). Nothing outside this list is claimed.

## Security design

- **No `exec`/`eval`/arbitrary Python.** The LLM produces data (JSON), never code.
- **Allowlists everywhere**: intents, operations, operators, chart types and date grains are `Literal` types; unknown values fail validation.
- **Column names are only ever looked up in the real schema**; values are used in comparisons with `regex=False`, so they can never become code or SQL.
- **Plan guard** (`security/plan_guard.py`): rejects forbidden keys (`code`, `sql`, `exec`, `url`...) and values containing dunder access, `exec(`, `import os`, `os.`/`subprocess`, shell commands, SQL statements, filesystem readers or URLs. The user's question is scanned too (prompt-injection attempts are stopped before reaching the LLM).
- **Result caps**: at most 1000 requested rows, 200 table rows and 1000 chart points returned.
- **Privacy**: datasets live only in server memory with a TTL, are never written to disk, and CSV contents are never logged (only ids and dimensions). The LLM sees schema/statistics and a few example values only. Chat history is kept in browser memory and is not persisted.

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/dataset/upload` | multipart `file` -> `{dataset_id, profile, preview, warnings}` |
| GET | `/api/dataset/{id}` | profile / metadata |
| GET | `/api/dataset/{id}/preview?page=&page_size=&search=` | paginated rows |
| POST | `/api/dataset/{id}/insights` | computed insights |
| DELETE | `/api/dataset/{id}` | delete from memory |
| GET / DELETE | `/api/dataset/{id}/history` | server-side Q&A context |
| POST | `/api/chat` | `{dataset_id, question}` -> answer, analysis, stat, table, chart |
| POST | `/api/chat/stream` | same, streamed as NDJSON stage events then the result |
| GET | `/api/health` | active planner, model, limits |

Example response:

```json
{
  "status": "ok",
  "answer": "The average of marks is 84.90.",
  "analysis": {"intent": "aggregation", "operation": "mean", "column": "marks",
               "explanation": "Calculated the average of the 'marks' column (missing values ignored).",
               "plan": {"intent": "aggregation", "operation": "mean", "column": "marks"}},
  "stat": {"label": "Average marks", "value": "84.90"},
  "table": null,
  "chart": null
}
```

`status` is one of `ok`, `unsupported`, `clarification`, `error`.

## Testing

```bash
cd backend
pytest -q
```

91 tests cover upload, invalid/empty/malformed/binary CSVs, encodings, duplicate columns, profiling, row count, averages, group-by, filtering, sorting, top/bottom N, chart generation, unknown column, unsupported questions, empty results, missing values, malicious AI plans (code/SQL/URL injection), invalid AI JSON (+retry), LLM failure, hallucinated columns, type errors, large-file/row limits, date grouping, history and the streaming endpoint. LLM behaviour is tested with a scripted fake client, so tests need no API key or network.

## Evaluation (accuracy, speed, tokens)

`backend/eval/` contains a reproducible evaluation. Ground truth is computed independently with pandas, so a question only passes when the **final answer** is correct.

```bash
cd backend
pip install -r eval/requirements-eval.txt                       # tiktoken, for token counting
PYTHONPATH=. python eval/run_eval.py --planner rules --set main      # 40 questions, offline
PYTHONPATH=. python eval/run_eval.py --planner rules --set heldout   # 25 differently-worded questions
PYTHONPATH=. python eval/run_eval.py --planner llm   --set main --delay 2     # uses OPENAI_* settings, no fallback
PYTHONPATH=. python eval/token_size.py                          # tokens sent per question vs pasting the CSV
```

Results are written to `backend/eval/results_*.json`. Measured so far (rule-based planner): 40/40 on the main set; 24/25 on the held-out set at first run (the miss exposed two real bugs, since fixed and covered by a regression test), 25/25 after. AI model (`openai/gpt-oss-120b` via Groq, evaluated without the rule-based fallback): 40/40 on the main set and 23/25 on the held-out set (misses: a filtered count that dropped the filter, and a false refusal for 'missing entries'); median 1,076 ms per question (rate-limit waiting excluded) and about 2,229 tokens in / 119 out per question, as counted by the provider. On Groq's free tier this model is capped at 8,000 tokens per minute, so the LLM run paces itself and takes ~20 minutes. The LLM run records the provider's own token counts and latency per question.

Every chat answer also carries a `usage` object (total / plan / execute milliseconds and, for the LLM planner, prompt and completion tokens), shown in the UI under "How this was calculated".

The slide deck `docs/ChatCSV-AI-Performance-Evaluation.pptx` summarises these results in plain language.

## Sample questions

Using `sample_data/students.csv` (click **Try sample students.csv** in the UI):

1. How many students are there?
2. What is the average marks?
3. Which department has the highest average marks?
4. Show the top 10 students by marks.
5. Show students with attendance below 75%.
6. What is the average marks by department?
7. Show a bar chart of average marks by department.
8. Is there a relationship between attendance and marks?
9. Show the distribution of marks.
10. What percentage of students are from CSE?
11. Which city has the most students?
12. Are there any missing values?
13. Show the lowest 5 students by marks.
14. What is the median attendance?
15. What is the correlation between marks and attendance?
16. What is the weather in Pune? *(refused: not in the dataset)*
17. What's the average salary? *(unknown column: lists available columns)*
18. Show students with marks above 90 or attendance below 60
19. What is the 90th percentile of marks?
20. Show the top 10% of students by marks
21. What is the rank of Kavya Bose by marks?
22. Show outliers in marks
23. Average marks by department and gender *(pivot table + grouped chart)*

## Known limitations

- Datasets and server-side history live in memory: a backend restart (or the TTL) clears them, and multi-instance deployments would need shared storage.
- Single-table analysis only (no joins across files), one dataset at a time in the UI.
- The rule-based fallback understands common phrasings, not arbitrary language; configure an LLM key for free-form questions.
- Pearson correlation only; no forecasting or statistical tests.
- Files up to 25 MB / 100k rows by default (configurable); everything is loaded into memory.
- Free ports 3000 and 8000 before `docker compose up`; if you run the dev server on another port, add it to `CORS_ORIGINS`.

## Future improvements

- Multi-condition OR logic and multi-column group-by / pivot tables
- Streaming LLM tokens and conversational summaries grounded in computed results
- Chunked/Parquet-backed storage (DuckDB/Polars) for large files
- Export results (CSV/PNG), saved dashboards, multiple datasets side by side
- Authentication and per-user dataset isolation

## How this satisfies PS 91

| Requirement | Where |
|---|---|
| Upload a CSV and chat in natural language | Upload zone + chat panel |
| Generate pandas-based analysis | Plan -> `executor.py` (pandas operations) |
| Safely execute | No `exec`/`eval`; schema + allowlist + guard + result validation |
| Answer, table or visualization | Stat cards, tables, Recharts charts from backend chart specs |
| Works on any CSV | Profiling and prompts are schema-driven; no hardcoded columns |
| Avoid hallucination | Out-of-scope refusal; answers written from computed results; insights computed, not generated |

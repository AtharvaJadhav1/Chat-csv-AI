# ChatCSV AI

> **Talk to your data. Get answers instantly.**

ChatCSV AI is an interactive tool for exploring CSV files using natural language. Upload a dataset, ask questions in plain English, and get answers backed by validated Pandas analysis — including summaries, tables, statistics, and charts.

The application converts questions into structured analysis plans, validates those plans, executes only supported operations, and presents results in an intuitive chat interface.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![Pandas](https://img.shields.io/badge/Pandas-2.2-150458)
![Docker](https://img.shields.io/badge/Docker-supported-2496ED)

## Contents

- [Why ChatCSV AI?](#why-chatcsv-ai)
- [Features](#features)
- [How It Works](#how-it-works)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Example Questions](#example-questions)
- [Supported Analysis](#supported-analysis)
- [API Reference](#api-reference)
- [Security and Data Handling](#security-and-data-handling)
- [Running Tests](#running-tests)
- [Evaluation](#evaluation)
- [Limitations](#limitations)
- [Contributing](#contributing)

## Why ChatCSV AI?

Working with CSV data often requires writing code, knowing the right formulas, or building charts manually. ChatCSV AI makes that process conversational.

Instead of writing a Pandas query, you can ask:

- "What is the average marks?"
- "Show the top 10 students by marks."
- "Which department has the highest average performance?"
- "Create a chart showing sales by month."

The application translates supported questions into a structured plan and calculates the answer from the uploaded dataset.

## Features

### Explore your data
- Upload CSV files through a drag-and-drop interface.
- Detect common encodings and delimiters.
- Validate malformed files, empty files, duplicate columns, and unsupported inputs.
- Automatically profile columns, data types, missing values, unique values, and descriptive statistics.
- Preview, search, and paginate through dataset rows.

### Ask questions in natural language
- Chat with your uploaded CSV using plain English.
- Ask follow-up questions using conversation context.
- Use an LLM planner or the built-in rule-based planner.
- Receive answers, statistical cards, tables, and visualizations.
- Get clear feedback for unsupported questions and unknown columns.

### Visualize and understand results
- Generate bar, line, pie, histogram, scatter, and area charts.
- Run automatic dataset insights.
- Explore missing values, correlations, outliers, distributions, and category leaders.
- See the calculation explanation associated with an answer.

### User experience
- Responsive dashboard and chat interface.
- Light and dark themes.
- Dataset preview, history, insights, and settings pages.
- Loading, empty, and error states.
- Streamed analysis-stage updates.

## How It Works

ChatCSV AI separates language understanding from data execution. The LLM does not execute Python code or directly manipulate the uploaded dataset.

```text
             CSV Upload
                 |
          File Validation
                 |
          Dataset Profiling
                 |
          In-Memory Dataset
                 |
User Question -> Planner (LLM / Rules)
                 |
          Structured JSON Plan
                 |
          Schema Validation
                 |
          Dataset / Column Validation
                 |
          Allowlisted Pandas Executor
                 |
          Result Validation
                 |
       Answer + Table + Chart Spec
                 |
          Next.js Interface
```

### Analysis pipeline

1. **Upload:** The backend reads and validates the CSV file.
2. **Profile:** Dataset columns, types, missing values, and statistics are calculated.
3. **Understand:** The planner receives the question, dataset schema, relevant statistics, and recent conversation context.
4. **Plan:** The planner produces a structured JSON analysis plan.
5. **Validate:** Pydantic schemas and dataset-aware checks validate the requested operation, columns, types, and values.
6. **Execute:** A fixed, allowlisted Pandas operation performs the requested calculation.
7. **Verify:** The result is checked for valid shape, size, and numeric values.
8. **Respond:** The backend builds the answer and optional table/chart specification for the frontend.

When an API key is not configured, the rule-based planner uses the same structured plan format. This allows the application to work without an external LLM.

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript |
| Styling | Tailwind CSS |
| Charts | Recharts |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Data processing | Pandas, NumPy |
| Validation | Pydantic, Pydantic Settings |
| AI integration | OpenAI-compatible Chat Completions API |
| Testing | Pytest |
| Containerization | Docker, Docker Compose |

## Project Structure

```text
Chat-csv-AI/
├── backend/
│   ├── app/
│   │   ├── api/             # API routes and dependencies
│   │   ├── models/          # Dataset storage models
│   │   ├── schemas/         # Request, response, and plan schemas
│   │   ├── security/        # Input and analysis-plan validation
│   │   ├── services/        # CSV, planner, executor, insights, chat
│   │   ├── utils/           # Formatting and JSON helpers
│   │   ├── config.py        # Application settings
│   │   └── main.py          # FastAPI application
│   ├── eval/                # Accuracy and token evaluation
│   ├── tests/               # Backend tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/                 # Next.js pages and routes
│   ├── components/          # UI components
│   ├── lib/                 # API client, context, utilities
│   ├── public/              # Static assets and sample CSVs
│   └── Dockerfile
├── sample_data/             # Example CSV datasets
├── docs/                    # Project documentation and evaluation deck
├── .env.example
├── docker-compose.yml
└── README.md
```

## Getting Started

### Prerequisites

For local development, install:

- Python 3.11 or later
- Node.js 20 or later
- npm
- Git

For the containerized setup, install Docker Desktop or Docker Engine with the Docker Compose plugin.

### 1. Clone the repository

```bash
git clone https://github.com/AtharvaJadhav1/Chat-csv-AI.git
cd Chat-csv-AI
```

### 2. Configure environment variables

Create a local environment file from the example:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

An LLM API key is optional. Leave `OPENAI_API_KEY` empty to use the offline rule-based planner.

### Option A: Run with Docker Compose

From the project root:

```bash
docker compose up --build
```

Once the services are running:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/health |

To stop the services:

```bash
docker compose down
```

### Option B: Run locally

**Start the backend**

Open a terminal:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment.

Windows PowerShell:

```powershell
.venv\\Scripts\\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install dependencies and start FastAPI:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The backend will be available at http://localhost:8000.

**Start the frontend**

Open another terminal from the repository root:

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at http://localhost:3000.

> **Note:** The frontend uses `NEXT_PUBLIC_API_URL` to determine which backend URL the browser calls. Configure it before building the frontend when using a non-default backend address. The Docker Compose configuration passes this variable as a frontend build argument.

## Environment Variables

Configure these values in the root `.env` file:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | Empty | API key for the LLM planner. Empty enables the rule-based planner. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base URL. |
| `LLM_MODEL` | `gpt-4o-mini` | Model name sent to the configured provider. |
| `LLM_TIMEOUT_SECONDS` | `30` | LLM request timeout. |
| `MAX_FILE_SIZE_MB` | `25` | Maximum CSV upload size in MB. |
| `MAX_ROWS` | `100000` | Maximum number of CSV rows accepted. |
| `DATASET_TTL_MINUTES` | `120` | Inactivity period before an in-memory dataset expires. |
| `CORS_ORIGINS` | Local frontend origins | Comma-separated list of allowed browser origins. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL used by the frontend. |

Never commit your real API keys or secrets. Keep your local `.env` file out of version control.

## Example Questions

Try these questions with the included `sample_data/students.csv` dataset:

| Question | Expected analysis |
|---|---|
| How many students are there? | Row count |
| What is the average marks? | Mean |
| What is the median attendance? | Median |
| Which department has the highest average marks? | Group-by and ranking |
| Show the top 10 students by marks. | Sorting and top N |
| Show students with attendance below 75%. | Filtering |
| What percentage of students are from CSE? | Percentage |
| Are there any missing values? | Missing-value analysis |
| What is the correlation between marks and attendance? | Correlation |
| Show the distribution of marks. | Histogram |
| Show students with marks above 90 or attendance below 60. | OR filtering |
| What is the 90th percentile of marks? | Percentile |
| Show outliers in marks. | IQR-based outlier analysis |
| Show average marks by department and gender. | Pivot / grouped analysis |

Questions outside the supported dataset-analysis scope are rejected rather than answered with unrelated or invented information.

## Supported Analysis

The analysis engine supports the following operations, subject to valid columns and data types:

- **Dataset information:** row count, column count, and column listing.
- **Aggregations:** mean, median, min, max, sum, count, and standard deviation.
- **Distinct values:** unique values, distinct counts, and value frequencies.
- **Filtering:** equality, inequality, comparisons, contains, membership, null checks, and combinations using OR / NOT.
- **Text conditions:** starts with, ends with, and contains.
- **Sorting and ranking:** ascending/descending sorting, top N, bottom N, and rank lookup.
- **Grouping:** group-by aggregations and pivot / crosstab analysis.
- **Missing data:** missing-value counts and analysis.
- **Statistics:** descriptive statistics, Pearson correlation, percentiles, and quartiles.
- **Distribution:** histograms and outlier detection using the 1.5 × IQR rule.
- **Dates:** date-range filtering and grouping by year, month, day, and weekday.
- **Visualizations:** bar, line, pie, histogram, scatter, and area chart specifications.

## API Reference

The backend exposes REST endpoints under the `/api` prefix.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Backend health, planner, model, and configured limits |
| `POST` | `/api/dataset/upload` | Upload and profile a CSV file |
| `GET` | `/api/dataset/{dataset_id}` | Retrieve dataset profile |
| `GET` | `/api/dataset/{dataset_id}/preview` | Retrieve paginated and searchable rows |
| `POST` | `/api/dataset/{dataset_id}/insights` | Generate dataset insights |
| `DELETE` | `/api/dataset/{dataset_id}` | Delete a dataset from memory |
| `GET` | `/api/dataset/{dataset_id}/history` | Retrieve server-side Q&A history |
| `DELETE` | `/api/dataset/{dataset_id}/history` | Clear Q&A history |
| `POST` | `/api/chat` | Ask a question about a dataset |
| `POST` | `/api/chat/stream` | Stream analysis stages and the final answer |

Interactive request and response schemas are available at http://localhost:8000/docs when the backend is running.

### Example chat request

```json
{
  "dataset_id": "your-dataset-id",
  "question": "What is the average marks?"
}
```

### Example response

```json
{
  "status": "ok",
  "answer": "The average of marks is 84.90.",
  "analysis": {
    "intent": "aggregation",
    "operation": "mean",
    "column": "marks",
    "explanation": "Calculated the average of the 'marks' column (missing values ignored)."
  },
  "stat": {
    "label": "Average marks",
    "value": "84.90"
  },
  "table": null,
  "chart": null
}
```

## Security and Data Handling

The application is designed to keep AI-generated plans separate from code execution.

- The LLM returns structured data; it does not return executable Python.
- No arbitrary `exec` or `eval` execution is used for analysis.
- Plans are checked against schemas, allowed operations, and the uploaded dataset.
- Unknown columns, invalid operations, and unsupported requests are rejected.
- Result sizes are capped to help prevent oversized responses.
- CSV data is held in backend memory with an inactivity-based TTL and is not written to disk by the dataset store.
- The LLM planner receives schema and profiling context rather than the complete CSV contents.
- Application logging records dataset dimensions and identifiers, not CSV cell contents.
- Chat history is maintained in browser memory and the backend's in-memory dataset record; it is not durable storage.

**Deployment note:** This project is not a substitute for a hardened multi-user data platform. Review authentication, authorization, network exposure, retention, and data-handling requirements before deploying with sensitive datasets.

## Running Tests

Backend tests use Pytest.

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

The test suite covers CSV validation, profiling, analysis operations, chart generation, invalid requests, security checks, LLM planner behaviour, history, and streaming responses.

## Evaluation

Reproducible evaluation scripts and recorded results are available under `backend/eval/`.

Install the evaluation dependency:

```bash
cd backend
pip install -r eval/requirements-eval.txt
```

Run the rule-based planner evaluation:

```bash
PYTHONPATH=. python eval/run_eval.py --planner rules --set main
PYTHONPATH=. python eval/run_eval.py --planner rules --set heldout
```

Run the LLM evaluation using the configured provider:

```bash
PYTHONPATH=. python eval/run_eval.py --planner llm --set main
```

Token usage evaluation:

```bash
PYTHONPATH=. python eval/token_size.py
```

Evaluation outputs are stored in `backend/eval/results_*.json`. The repository also includes a performance evaluation presentation in `docs/ChatCSV-AI-Performance-Evaluation.pptx`.

## Limitations

- Dataset storage and server-side history are in memory. Restarting the backend or reaching the TTL clears them.
- The current application is designed around one active dataset per user session.
- Only single-dataset analysis is supported; joins across multiple uploaded files are not implemented.
- Rule-based planning handles common question patterns. An LLM provider is recommended for more flexible natural-language phrasing.
- Correlation is Pearson correlation; forecasting and advanced statistical tests are outside the current scope.
- Default upload limits are 25 MB and 100,000 rows, configurable through environment variables.
- Multi-instance deployments require shared storage and an appropriate session strategy.

## Contributing

Contributions, bug reports, and feature suggestions are welcome.

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Make your changes and add or update tests where appropriate.
4. Run the backend test suite.
5. Open a pull request with a clear description of the change.

## Author

**Atharva Jadhav**

- GitHub: [@AtharvaJadhav1](https://github.com/AtharvaJadhav1)
- Project: [ChatCSV AI](https://github.com/AtharvaJadhav1/Chat-csv-AI)

---

<p align="center">
  Built to make data analysis more accessible through natural language.
</p>

# Compass AI

Compass AI helps employees find cited AI policy guidance and routes formal decisions through assigned human reviewers. The demo uses synthetic policies, tool and model catalogs, and case records.

## Run locally

Use Python 3.12 and uv.

```sh
uv venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.lock
./run-web.sh
```

Open http://127.0.0.1:8600/. The default local mode retrieves policy extracts and case facts using embedded Qdrant, BM25 and SQLite.

For live mode, copy `.env.example` to `.env`, set `COMPASS_MODE=live` and enter your OpenAI API key locally. Restart the server. Live mode uses OpenAI embeddings and GPT-5.4 Mini to generate cited guidance. Keep credentials in the ignored environment file.

## Architecture

- Custom HTML, CSS and JavaScript frontend with FastAPI and Uvicorn.
- LangChain and LangGraph for context resolution, hybrid retrieval, evidence assembly, answer generation and citation checks.
- Embedded Qdrant for the published knowledge index and separate upload candidates. SQLite stores requests, decisions, conditions, audit events and evaluation runs.
- Docker Compose configures PostgreSQL and a Qdrant server. LangSmith tracing and model judging are optional.

Sources #1–7 and #9 feed knowledge retrieval. Sources #8 and #10–12 contain operational records. The evaluation JSONL contains 50 cases, split into 30 development and 20 holdout cases.

The demo persona selector uses synthetic identities. Human reviewers retain authority for decisions and release clearance.

## Verify

```sh
.venv/bin/python -m pytest -q
```

The checked-in development evaluation is from local evidence mode. Live generation and citation-reference checks passed a smoke test. Semantic faithfulness and live p95 latency remain to be measured.

The earlier Streamlit interface is available through `./run.sh`.

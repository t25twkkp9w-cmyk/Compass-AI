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

## Week 6 AI Compass Assurance

The local Week 6 extension adds three defenses: retrieved-evidence quarantine, token-bound API identities, and complete-response sensitive-output screening. See `assurance/ASSESSMENT-REPORT.html` for the executed 30-case baseline and retest, limitations, and attack-to-defense mapping.

Protected demonstration mode requires `COMPASS_AUTH_MODE=token` and `COMPASS_TEST_TOKENS`, a private JSON mapping of random credentials of at least 32 characters to fixed synthetic actor IDs. Configure these in ignored `.env`. Use the sign-in form; the credential is stored in an HttpOnly SameSite cookie. Use HTTPS outside localhost. An authorized principal still needs case assignment and workflow permissions. Missing/invalid credentials fail closed. `COMPASS_AUTH_MODE=demo` retains the original explicit persona demonstration; it is not authenticated access. This is a controlled demo credential mechanism, not enterprise SSO.

Run `python -m pytest -q` for regression and defense tests. With a local-mode protected server on port 8601 and locally configured test credentials, `node tests/assurance-ui.test.cjs` exercises browser DOM sign-in, identity binding, guidance, and sign-out. Install package.json development dependencies first.

`python assurance/run_assessment.py --phase defended` runs the live-model test register and overwrites the defended result file. Preserve evidence before deliberate reruns. Run the baseline only from original commit `45c5e162d494a025b0414f8f07e69fd9b39531d6` with the runner copied into that checkout. The phase flag is an evidence label, not a defense toggle. All private configurations and runtime indexes are ignored by Git.

Pattern-based injection and output checks have deliberately bounded coverage. They do not establish universal attack resistance, and output screening does not prevent sensitive inputs from reaching a model. Use synthetic sensitive fixtures only.

# PaperGraph AI

[![CI](https://github.com/vsokoltsov/papergraph-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/vsokoltsov/papergraph-ai/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/vsokoltsov/papergraph-ai/branch/main/graph/badge.svg)](https://codecov.io/gh/vsokoltsov/papergraph-ai)

## 🧩 Problem Description

PaperGraph AI helps researchers explore scientific papers from OpenAlex with an agentic AI
workflow. The app ingests paper metadata and abstracts, stores semantic content in Qdrant, stores
paper relationships in Neo4j, and lets an LLM agent combine vector retrieval with graph context.

The main goal is to answer research questions such as:

- Which papers discuss a specific topic?
- How do papers relate by topic, source, author, institution, or citation?
- What are the main research directions across a retrieved set of papers?

The system is built around an automated ingestion pipeline, an agentic retrieval layer, evaluation
scripts, feedback collection, and Grafana monitoring dashboards.

## 💬 UI Interface

The user interface is a Streamlit chat app.

It provides:

- A chat input for research questions.
- Real-time agent progress in the research section.
- Final answers generated from retrieved paper context.
- Feedback buttons for marking answers as useful or not useful.
- Backend streaming from the FastAPI API to the UI.

Local URLs:

- 🖥️ Streamlit UI: `http://localhost:8501`
- 🚀 FastAPI backend: `http://localhost:8000`
- 📊 Grafana dashboards: `http://localhost:3000`
- 📈 Prometheus: `http://localhost:9090`
- 🧠 Neo4j Browser: `http://localhost:7474`
- 🔎 Qdrant API: `http://localhost:6333`

## 🚀 How To Run The Project

Install dependencies:

```bash
uv sync
```

Start the infrastructure:

```bash
docker compose up -d
```

Run migrations:

```bash
uv run alembic upgrade heads
```

Ingest papers from OpenAlex with dlt:

```bash
uv run python -m app.ingestion.run "mathematics" --limit 10
```

Start the backend locally:

```bash
make backend
```

Start the UI locally:

```bash
make ui
```

Alternatively, the API and UI are also included in `docker-compose.yml`, so a full Docker run is:

```bash
docker compose up -d --build
```

Run checks:

```bash
make check
```

## LLM Evaluation

The project uses the course-style LLM evaluation flow:

1. Ingest papers into Qdrant and Neo4j.
2. Use the committed frozen ground-truth examples in `app/eval/llm/llm_dataset.json`.
3. Run the real PaperGraph agent for each evaluation question.
4. Use an LLM-as-a-judge to compare the generated agent answer with the ground-truth answer.
5. Use the same judge to evaluate the agent trajectory, meaning the tool calls made before the final answer.

The generated ground-truth dataset has this shape:

```json
{
  "question": "What does this paper say about graph retrieval?",
  "answer_orig": "Ground-truth answer generated from the source paper data.",
  "document": "https://openalex.org/W..."
}
```

`answer_orig` is the expected answer. `answer_agent` is produced later by running the actual app agent. The evaluator sends both answers, the original question, the source document ID, and the recorded tool calls to the judge.

### Compared Approaches

LLM evaluation compares three retrieval/tool-use variants:

- `vector_only`: the agent can only use Qdrant vector search.
- `graph_only`: the agent can only use Neo4j graph search and graph context.
- `vector_plus_graph`: the agent uses Qdrant vector search first, then Neo4j graph context for the returned OpenAlex IDs.

The evaluation summary reports `answer_good_rate` and `trajectory_good_rate` per approach. The best approach should be selected from the current evaluation output. At this stage, `vector_only` is the default baseline to beat, while `vector_plus_graph` is useful when the graph context improves the answer without adding unnecessary tool calls.

The frozen dataset intentionally mixes direct paper questions, semantic paraphrases, and cross-paper graph-context questions. This avoids evaluating only exact title or abstract keyword lookup. The graph-context questions ask the agent to compare papers by topic, application domain, and relationship-style context, which is where `vector_plus_graph` should have an advantage over pure vector search.

### Run Locally

Start databases and run migrations:

```bash
docker compose up -d qdrant neo4j postgres
uv run alembic upgrade heads
```

Ingest papers:

```bash
uv run python -m app.cli "knowledge graph based retrieval augmented generation" --limit 10
```

Run the cheap LLM smoke evaluation from the committed frozen dataset:

```bash
uv run python -m app.eval.llm.evaluate \
  --dataset app/eval/llm/llm_dataset.json \
  --output-format markdown \
  --limit 2 \
  --approaches vector_only vector_plus_graph
```

Run the full LLM evaluation locally when you need benchmark numbers:

```bash
uv run python -m app.eval.llm.evaluate \
  --dataset app/eval/llm/llm_dataset.json \
  --output-format markdown
```

Write Markdown and JSON artifacts from the same evaluator run:

```bash
uv run python -m app.eval.llm.evaluate \
  --dataset app/eval/llm/llm_dataset.json \
  --output-format markdown \
  --output-dir eval-results
```

To regenerate candidate ground-truth data locally, ingest the focused query first and then run:

```bash
uv run python -m app.eval.llm.ground_truth.evaluate \
  --source qdrant \
  --limit 10 \
  --questions-per-document 1 \
  --output app/eval/llm/generated_dataset.json
```

Generated datasets and evaluation outputs are ignored by Git. The committed LLM dataset is intentionally frozen so CI runs can be compared across builds. If a regenerated dataset is better, review it manually before replacing `app/eval/llm/llm_dataset.json`.

### CI

GitHub Actions runs an `llm-eval` job after tests. The job starts Qdrant and Neo4j, runs migrations, ingests a focused batch of Graph RAG papers, runs the LLM judge against the frozen dataset, writes the markdown summary to the Actions summary, and uploads JSON/markdown artifacts generated from the same evaluator run.

Push and pull-request builds run only the smoke LLM evaluation: two questions and the `vector_only` / `vector_plus_graph` approaches. Use the manual `workflow_dispatch` run with `llm_eval_mode=full` for the complete LLM benchmark.

The job is marked `continue-on-error` because it depends on external services and API keys. This keeps normal CI useful while still producing evaluation artifacts when the environment is available.

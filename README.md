# PaperGraph AI

[![CI](https://github.com/vsokoltsov/papergraph-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/vsokoltsov/papergraph-ai/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/vsokoltsov/papergraph-ai/branch/main/graph/badge.svg)](https://codecov.io/gh/vsokoltsov/papergraph-ai)

## LLM Evaluation

The project uses the course-style LLM evaluation flow:

1. Ingest papers into Qdrant and Neo4j.
2. Generate ground-truth examples from the ingested paper data.
3. Run the real PaperGraph agent for each generated question.
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

The evaluation summary reports `answer_good_rate` and `trajectory_good_rate` per approach. The intended production approach is `vector_plus_graph`, because it combines semantic matching from Qdrant with relationship context from Neo4j.

### Run Locally

Start databases and run migrations:

```bash
docker compose up -d qdrant neo4j
uv run alembic upgrade head
```

Ingest papers:

```bash
uv run python -m app.cli "graph rag" --limit 5
```

Generate ground truth from the ingested Qdrant data:

```bash
uv run python -m app.eval.llm.ground_truth.evaluate \
  --source qdrant \
  --limit 5 \
  --questions-per-document 1 \
  --output app/eval/llm/ground_truth/ground_truth_dataset.json
```

Run LLM evaluation:

```bash
uv run python -m app.eval.llm.evaluate \
  --dataset app/eval/llm/ground_truth/ground_truth_dataset.json \
  --output-format markdown
```

Generated datasets and evaluation outputs are ignored by Git. The committed `dataset.json` files are small seed examples; generated files depend on current database contents and model responses.

### CI

GitHub Actions runs an `llm-eval` job after tests. The job starts Qdrant and Neo4j, runs migrations, ingests a small batch of papers, generates ground truth, runs the LLM judge, writes the markdown summary to the Actions summary, and uploads JSON/markdown artifacts.

The job is marked `continue-on-error` because it depends on external services and API keys. This keeps normal CI useful while still producing evaluation artifacts when the environment is available.

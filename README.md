# PaperGraph AI

[![CI](https://github.com/vsokoltsov/papergraph-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/vsokoltsov/papergraph-ai/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/vsokoltsov/papergraph-ai/branch/main/graph/badge.svg)](https://codecov.io/gh/vsokoltsov/papergraph-ai)

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
docker compose up -d qdrant neo4j
uv run alembic upgrade head
```

Ingest papers:

```bash
uv run python -m app.cli "knowledge graph based retrieval augmented generation" --limit 10
```

Run LLM evaluation from the committed frozen dataset:

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

The job is marked `continue-on-error` because it depends on external services and API keys. This keeps normal CI useful while still producing evaluation artifacts when the environment is available.

# PaperGraph AI --- Complete Project Context for Codex

> This document is intended to be shared with Codex as the complete
> architectural context for the project. It summarizes all design
> decisions made during the planning discussion. The goal is to preserve
> the reasoning behind the architecture rather than only describing the
> final implementation.

# Project

**Name:** PaperGraph AI

**Subtitle**

> PaperGraph AI --- An Agentic Graph RAG Platform for Scientific
> Literature Exploration

------------------------------------------------------------------------

# Project Goal

The goal is to build the final project for **LLM Zoomcamp**.

The objective is **not** to build another basic RAG chatbot.

Instead, the project should demonstrate a modern production-like GenAI
architecture using:

-   Agentic RAG
-   Graph RAG
-   Vector RAG
-   Workflow orchestration
-   Automated ingestion
-   Graph databases
-   Vector databases
-   Evaluation
-   Monitoring

The application should allow a user to create a topic-specific knowledge
base from scientific literature and then explore that knowledge through
natural language.

------------------------------------------------------------------------

# Problem Statement

Researchers frequently spend significant time navigating scientific
literature.

Existing tools such as Google Scholar or Semantic Scholar are excellent
search engines but are not designed to answer reasoning-heavy questions
like:

-   Which papers introduced a concept?
-   Which papers connect two research areas?
-   What is the citation path between Paper A and Paper B?
-   Who are the key authors in this field?
-   Which institutions contribute most to a topic?
-   Why was a paper selected as evidence?

PaperGraph AI should solve this by combining semantic retrieval, graph
traversal and an AI agent capable of selecting the proper retrieval
strategy.

------------------------------------------------------------------------

# Selected Dataset

Primary source:

-   OpenAlex

Future extensions:

-   Semantic Scholar
-   arXiv

The user builds a custom knowledge base for a selected topic instead of
downloading the entire OpenAlex corpus.

Example:

Topic:

Graph RAG

Parameters:

-   max papers
-   traversal depth

------------------------------------------------------------------------

# Overall Architecture

``` text
                Streamlit UI
                      │
                      ▼
                 FastAPI Backend
          ┌───────────┴────────────┐
          │                        │
          ▼                        ▼
   Kestra Ingestion          LangGraph Agent
          │                        │
          ▼                        ▼
 OpenAlex / Semantic        Neo4j + Qdrant
     Scholar APIs                │
          │                      │
          └────────────┬─────────┘
                       ▼
                      LLM
```

------------------------------------------------------------------------

# Component Responsibilities

## Streamlit

Responsible for:

-   Build Knowledge Base page
-   Ask Research Agent page
-   Progress monitoring
-   Displaying sources
-   Displaying graph paths
-   Displaying retrieved papers
-   Displaying execution status

------------------------------------------------------------------------

## FastAPI

Acts as a thin backend layer.

Endpoints:

-   POST /ingest
-   GET /ingest/{execution_id}
-   POST /chat

FastAPI communicates with:

-   Kestra
-   LangGraph

Streamlit never talks directly to Kestra.

------------------------------------------------------------------------

## Kestra

Kestra is **only an orchestration engine**.

It should NOT contain business logic.

Responsibilities:

-   Execute workflows
-   Trigger Python tasks
-   Retry failed tasks
-   Execution history
-   Logs
-   Scheduling
-   Monitoring

The ingestion logic itself lives in Python modules.

------------------------------------------------------------------------

## dlt

dlt is responsible for:

-   Reading data from OpenAlex
-   Pagination
-   Incremental loading
-   Schema evolution
-   Writing staging tables

It should not load directly into Neo4j or Qdrant.

Instead:

``` text
OpenAlex
    ↓
dlt
    ↓
DuckDB staging
```

------------------------------------------------------------------------

## DuckDB

Acts as a staging layer.

Advantages:

-   reproducibility
-   debugging
-   SQL inspection
-   restart pipeline without re-downloading

Tables:

-   papers
-   authors
-   topics
-   citations

------------------------------------------------------------------------

## Neo4j

Graph database.

Stores:

Paper

Author

Institution

Venue

Topic

Relationships:

Paper -\> CITES -\> Paper

Author -\> WROTE -\> Paper

Paper -\> HAS_TOPIC -\> Topic

------------------------------------------------------------------------

## Qdrant

Vector database.

Embeddings are created from:

-   title
-   abstract

Payload:

-   paper_id
-   title
-   authors
-   year
-   url

------------------------------------------------------------------------

## LangGraph

LangGraph is NOT related to Neo4j.

LangGraph controls the AI workflow.

Typical execution:

Question

↓

Planner

↓

Graph Search?

↓

Vector Search?

↓

Merge Context

↓

LLM

↓

Answer

------------------------------------------------------------------------

# Ingestion Pipeline

User enters:

-   Topic
-   Max papers
-   Traversal depth

Pipeline:

Search OpenAlex

↓

Download papers

↓

Download citations

↓

Download references

↓

Normalize

↓

Generate embeddings

↓

Load Neo4j

↓

Load Qdrant

Each stage is an independent Python module.

Kestra orchestrates these modules.

------------------------------------------------------------------------

# QA Pipeline

Kestra is NOT involved.

Question

↓

LangGraph

↓

Neo4j

↓

Qdrant

↓

LLM

↓

Answer

------------------------------------------------------------------------

# User Interface

## Build Knowledge Base

Inputs:

-   Topic
-   Max papers
-   Depth

Button:

Build Knowledge Base

Display:

Running

Completed

Failed

Progress:

✅ fetch_openalex

✅ normalize

🔄 generate_embeddings

⏳ load_neo4j

⏳ load_qdrant

Progress should initially be implemented using polling against FastAPI.

WebSockets are unnecessary for the MVP.

------------------------------------------------------------------------

## Ask Research Agent

Chat interface.

Display:

-   Answer
-   Sources
-   Retrieved papers
-   Citation path
-   Tools used
-   Optional reasoning trace

------------------------------------------------------------------------

# Kestra Monitoring

Recommended approach:

Streamlit

↓

GET /status

↓

FastAPI

↓

Kestra API

↓

Execution state

Current task

Completed tasks

Logs

Polling every 2--5 seconds is sufficient for MVP.

------------------------------------------------------------------------

# Recommended Repository Structure

``` text
papergraph-ai/
├── app/
│   └── streamlit_app.py
├── api/
│   ├── main.py
│   └── schemas.py
├── agents/
│   ├── qa_agent.py
│   ├── tools.py
│   └── prompts.py
├── ingestion/
│   ├── dlt_openalex.py
│   ├── normalize.py
│   ├── embeddings.py
│   ├── load_neo4j.py
│   ├── load_qdrant.py
│   └── models.py
├── flows/
│   └── ingest_topic.yml
├── db/
│   ├── neo4j_schema.cypher
│   └── qdrant_setup.py
├── configs/
├── tests/
├── docker-compose.yml
├── README.md
└── .env.example
```

------------------------------------------------------------------------

# Incremental Development Plan

## Phase 0 --- Infrastructure

-   Docker Compose
-   Neo4j
-   Qdrant
-   DuckDB
-   FastAPI
-   Streamlit

------------------------------------------------------------------------

## Phase 1 --- MVP (No Kestra Yet)

Goal: Build a fully working vertical slice before introducing
orchestration.

Implement:

-   OpenAlex client
-   dlt ingestion
-   DuckDB staging
-   Neo4j loader
-   Qdrant loader
-   Simple vector RAG
-   Streamlit UI

Run via CLI:

``` bash
python ingest_topic.py --topic "Graph RAG" --max-papers 100
```

------------------------------------------------------------------------

## Phase 2 --- Introduce Kestra

Replace manual execution with Kestra.

Kestra simply orchestrates the existing Python modules.

No business logic should move into YAML.

------------------------------------------------------------------------

## Phase 3 --- Graph RAG

Implement graph tools:

-   Find authors
-   Citation neighbours
-   Citation path
-   Most influential papers
-   Topic graph

------------------------------------------------------------------------

## Phase 4 --- Agentic RAG

Introduce LangGraph.

Register tools:

-   Graph search
-   Vector search
-   Paper lookup
-   OpenAlex lookup

Planner decides which tools to invoke.

------------------------------------------------------------------------

## Phase 5 --- Retrieval Evaluation

Compare:

-   Vector search
-   Graph search
-   Hybrid Graph + Vector search

Choose the best.

------------------------------------------------------------------------

## Phase 6 --- LLM Evaluation

Evaluate multiple prompting strategies.

Keep the best-performing prompt.

------------------------------------------------------------------------

## Phase 7 --- Monitoring

Collect:

-   User feedback
-   Ingestion metrics
-   Retrieval metrics

Build dashboard.

------------------------------------------------------------------------

## Phase 8 --- Production Polish

-   Retries
-   Idempotent ingestion
-   Logging
-   Tests
-   Caching
-   Documentation

------------------------------------------------------------------------

# Design Principles

-   Kestra orchestrates only.
-   Business logic lives in Python.
-   dlt handles ingestion.
-   DuckDB is the staging layer.
-   Neo4j stores graph knowledge.
-   Qdrant stores vectors.
-   LangGraph performs agent orchestration.
-   FastAPI exposes APIs.
-   Streamlit provides the UI.

------------------------------------------------------------------------

# LLM Zoomcamp Evaluation Criteria

``` text
## Evaluation Criteria

Use these criteria to score the project:

* Problem description
    * 0 points: The problem is not described
    * 1 point: The problem is described but briefly or unclearly
    * 2 points: The problem is well-described and it's clear what problem the project solves
* Retrieval flow
    * 0 points: No knowledge base or LLM is used
    * 1 point: No knowledge base is used, and the LLM is queried directly
    * 2 points: Both a knowledge base and an LLM are used in the flow
* Retrieval evaluation
    * 0 points: No evaluation of retrieval is provided
    * 1 point: Only one retrieval approach is evaluated
    * 2 points: Multiple retrieval approaches are evaluated, and the best one is used
* LLM evaluation
    * 0 points: No evaluation of final LLM output is provided
    * 1 point: Only one approach (e.g., one prompt) is evaluated
    * 2 points: Multiple approaches are evaluated, and the best one is used
* Interface
   * 0 points: No way to interact with the application at all
   * 1 point: Command line interface, a script, or a Jupyter notebook
   * 2 points: UI (e.g., Streamlit), web application (e.g., Django), or an API (e.g., built with FastAPI)
* Ingestion pipeline
   * 0 points: No ingestion
   * 1 point: Semi-automated ingestion of the dataset into the knowledge base, e.g., with a Jupyter notebook
   * 2 points: Automated ingestion with a Python script or a special tool (e.g., Mage, dlt, Airflow, Prefect)
* Monitoring
   * 0 points: No monitoring
   * 1 point: User feedback is collected OR there's a monitoring dashboard
   * 2 points: User feedback is collected and there's a dashboard with at least 5 charts
* Containerization
    * 0 points: No containerization
    * 1 point: Dockerfile is provided for the main application OR there's a docker-compose for the dependencies only
    * 2 points: Everything is in docker-compose
* Reproducibility
    * 0 points: No instructions on how to run the code, the data is missing, or it's unclear how to access it
    * 1 point: Some instructions are provided but are incomplete, OR instructions are clear and complete, the code works, but the data is missing
    * 2 points: Instructions are clear, the dataset is accessible, it's easy to run the code, and it works. The versions for all dependencies are specified.
* Best practices
    * [ ] Hybrid search: combining both text and vector search (at least evaluating it) (1 point)
    * [ ] Document re-ranking (1 point)
    * [ ] User query rewriting (1 point)
* Bonus points (not covered in the course)
    * [ ] Deployment to the cloud (2 points)
    * [ ] Up to 3 extra bonus points if you want to award for something extra (write in feedback for what)
```

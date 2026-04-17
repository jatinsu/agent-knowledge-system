# Agent Knowledge System — Demo Run (multiarch-tuning-operator)

This document summarizes what the project does, how to run it against a GitHub repository, and a **verbatim session log** of commands, retrieval queries, and outputs from **2026-04-17**.

## What this project is

**Agent Knowledge System** ingests GitHub PR metadata (and optionally Jira), builds **features**, materializes a **JSON knowledge graph** (typed nodes and edges), and generates **AGENTS.md** / **ARCHITECTURE.md**. A **Retrieval Agent** loads the graph, classifies query intent via the LLM gateway, extracts entities, resolves nodes, runs **BFS traversal** (≤3 hops, bounded context), and returns compressed context for downstream use.

**Constraints** (see `README.md` / `CLAUDE.md`): graph-first docs, retrieval-only structured context, 3-hop cap, 700-line context budget, centralized Gemini gateway.

## Prerequisites

- Python ≥ 3.11  
- `pip install -e ".[dev]"`  
- `.env` with at least `GEMINI_API_KEY`; `GITHUB_TOKEN` recommended for GitHub API rate limits  
- Network access for GitHub API and Gemini  

## Target repository

- **Remote:** [https://github.com/outrigger-project/multiarch-tuning-operator](https://github.com/outrigger-project/multiarch-tuning-operator)  
- **CLI:** `--owner outrigger-project --repo multiarch-tuning-operator`

---

## Session log (commands, queries, outputs)

### 1. Install and initialize database

**Command:**

```bash
cd /Users/kpais/kpais-workspace/agent-knowledge-system-gemini
pip install -e ".[dev]" -q
python -m src.cli init
```

**Output:**

```
Initializing database...
Database initialized successfully!
```

### 2. Full workflow (ingest → features → graph → docs)

**Command:**

```bash
python -m src.cli full-workflow --owner outrigger-project --repo multiarch-tuning-operator --output-dir docs_demo_mtao
```

**Output:**

```
Step 1: Ingesting GitHub data...
2026-04-17 22:05:39 - src.ingestors.github_ingestor - INFO - Fetching repository outrigger-project/multiarch-tuning-operator
2026-04-17 22:05:39 - src.ingestors.github_ingestor - INFO - Fetching PRs for outrigger-project/multiarch-tuning-operator (limit=50)
2026-04-17 22:05:40 - src.ingestors.github_ingestor - INFO - Fetched 50 PRs from outrigger-project/multiarch-tuning-operator
  ✓ Ingested 50 PRs
Step 2: Building features...
  ✓ Built 50 features
Step 3: Building knowledge graph...
2026-04-17 22:06:15 - src.graph.storage - INFO - Saving knowledge graph to knowledge_graph.json
2026-04-17 22:06:15 - src.graph.storage - INFO - ✓ Saved graph: 101 nodes, 100 edges
2026-04-17 22:06:15 - src.graph.storage - INFO -   Checksum: c545b8ac91a74c9c...
2026-04-17 22:06:15 - src.graph.storage - INFO -   Version saved: graph_v20260417_163615.json
  ✓ Graph: 101 nodes, 100 edges
Step 4: Generating documentation...
  ✓ Generated documentation in docs_demo_mtao/

✓ Workflow complete!
```

**Artifacts:**

- `knowledge_graph.json` — current graph (also versioned under `graph_versions/`)  
- `docs_demo_mtao/AGENTS.md`, `docs_demo_mtao/ARCHITECTURE.md`  

**Excerpt (`docs_demo_mtao/AGENTS.md`):**

```markdown
# AGENTS.md

Repository Knowledge Graph Entry Point
...
## Graph Statistics
- Total Concepts: 50
- Total ADRs: 0
- Total Execution Plans: 0
```

### 3. Validate graph

**Command:**

```bash
python -m src.cli validate
```

**Output:**

```
2026-04-17 22:06:32 - src.graph.storage - INFO - Loading knowledge graph from knowledge_graph.json
2026-04-17 22:06:32 - src.graph.storage - INFO - ✓ Loaded graph: 101 nodes, 100 edges
Validating knowledge graph...
Graph valid: True
Nodes: 101
Edges: 100

Coverage:
  Concepts: 50
  ADRs: 0
  Plans: 0
  Meets minimum: False
```

### 4. Retrieval agent — Query A

**Query:** `What is the multiarch tuning operator and what problem does it solve?`

**Command:**

```bash
python -m src.cli retrieve "What is the multiarch tuning operator and what problem does it solve?"
```

**Output:**

```
2026-04-17 22:06:20 - src.graph.storage - INFO - Loading knowledge graph from knowledge_graph.json
2026-04-17 22:06:20 - src.graph.storage - INFO - ✓ Loaded graph: 101 nodes, 100 edges
Query: What is the multiarch tuning operator and what problem does it solve?
2026-04-17 22:06:20 - src.agents.retrieval - INFO - Retrieving context for query: What is the multiarch tuning operator and what problem does it solve?
2026-04-17 22:06:22 - src.agents.retrieval - WARNING - Failed to parse entities JSON: Expecting value: line 1 column 1 (char 0)
2026-04-17 22:06:22 - src.agents.retrieval - INFO - No direct entity matches, using entry points
2026-04-17 22:06:22 - src.agents.retrieval - INFO - BFS traversal: 1 start nodes → 50 results (max_hops=3, visited=100)
2026-04-17 22:06:22 - src.agents.retrieval - INFO - Retrieved 50 nodes, 635 lines in 2263.15ms

Intent: CONCEPT
Entities: 
Matched nodes: 1
Related nodes: 50
Context lines: 635

--- Context ---
# EntryPoint: AGENTS.md
Description: Repository documentation entry point

# Concept: WIP: feat: proposal for CEL expression placement plugin
Description: Feature implementation

# Concept: CodeRabbit Review Feedback
Description:  ## Address CodeRabbit Review Feedback                                                                                                                                                                                           
                                           ...
```

*(The CLI prints only the first ~500 characters of context; full bundled context is up to `MAX_CONTEXT_LINES`.)*

### 5. Retrieval agent — Query B

**Query:** `How does the operator reconcile NodePool or multi-architecture workloads?`

**Command:**

```bash
python -m src.cli retrieve "How does the operator reconcile NodePool or multi-architecture workloads?"
```

**Output:**

```
2026-04-17 22:06:20 - src.graph.storage - INFO - Loading knowledge graph from knowledge_graph.json
2026-04-17 22:06:20 - src.graph.storage - INFO - ✓ Loaded graph: 101 nodes, 100 edges
Query: How does the operator reconcile NodePool or multi-architecture workloads?
2026-04-17 22:06:20 - src.agents.retrieval - INFO - Retrieving context for query: How does the operator reconcile NodePool or multi-architecture workloads?
2026-04-17 22:06:22 - src.agents.retrieval - WARNING - Failed to parse entities JSON: Expecting value: line 1 column 1 (char 0)
2026-04-17 22:06:22 - src.agents.retrieval - INFO - No direct entity matches, using entry points
2026-04-17 22:06:22 - src.agents.retrieval - INFO - BFS traversal: 1 start nodes → 50 results (max_hops=3, visited=100)
2026-04-17 22:06:22 - src.agents.retrieval - INFO - Retrieved 50 nodes, 635 lines in 2104.92ms

Intent: IMPLEMENTATION
Entities: 
Matched nodes: 1
Related nodes: 50
Context lines: 635

--- Context ---
# EntryPoint: AGENTS.md
Description: Repository documentation entry point

# Concept: WIP: feat: proposal for CEL expression placement plugin
Description: Feature implementation

# Concept: CodeRabbit Review Feedback
Description:  ## Address CodeRabbit Review Feedback                                                                                                                                                                                           
                                           ...
```

### 6. Retrieval agent — Query C (keyword-heavy)

**Query:** `PodPlacementConfigs teardown operand resources ClusterPodPlacementConfig`

**Command:**

```bash
python -m src.cli retrieve "PodPlacementConfigs teardown operand resources ClusterPodPlacementConfig"
```

**Output:**

```
2026-04-17 22:06:32 - src.graph.storage - INFO - Loading knowledge graph from knowledge_graph.json
2026-04-17 22:06:32 - src.graph.storage - INFO - ✓ Loaded graph: 101 nodes, 100 edges
Query: PodPlacementConfigs teardown operand resources ClusterPodPlacementConfig
2026-04-17 22:06:32 - src.agents.retrieval - INFO - Retrieving context for query: PodPlacementConfigs teardown operand resources ClusterPodPlacementConfig
2026-04-17 22:06:34 - src.agents.retrieval - WARNING - Failed to parse entities JSON: Expecting value: line 1 column 1 (char 0)
2026-04-17 22:06:34 - src.agents.retrieval - INFO - No direct entity matches, using entry points
2026-04-17 22:06:34 - src.agents.retrieval - INFO - BFS traversal: 1 start nodes → 50 results (max_hops=3, visited=100)
2026-04-17 22:06:34 - src.agents.retrieval - INFO - Retrieved 50 nodes, 635 lines in 2046.09ms

Intent: IMPLEMENTATION
Entities: 
Matched nodes: 1
Related nodes: 50
Context lines: 635

--- Context ---
# EntryPoint: AGENTS.md
Description: Repository documentation entry point

# Concept: WIP: feat: proposal for CEL expression placement plugin
Description: Feature implementation

# Concept: CodeRabbit Review Feedback
Description:  ## Address CodeRabbit Review Feedback                                                                                                                                                                                           
                                           ...
```

### 7. Automated tests (project health)

**Command:**

```bash
pytest src/tests/ -q --tb=no
```

**Output:**

```
19 passed, 3 warnings in 0.40s
```

---

## Evaluation summary

| Area | Result |
|------|--------|
| **Ingestion** | 50 PRs fetched; 50 features built |
| **Knowledge graph** | 101 nodes, 100 edges; saved to `knowledge_graph.json`; validator reports **Graph valid: True** |
| **Documentation** | `docs_demo_mtao/AGENTS.md` and `ARCHITECTURE.md` generated |
| **Retrieval** | Intent classification succeeded (e.g. CONCEPT vs IMPLEMENTATION). Entity extraction **returned non-JSON** in these runs, so the agent **fell back to entry points** and BFS; behavior is consistent but **keyword-based `resolve_nodes` did not engage** without entities |
| **Coverage gate** | `validate` reports **Meets minimum: False** (0 ADRs / 0 plans in this build) |
| **Tests** | 19 tests passed |

## Typical commands (reference)

| Goal | Command |
|------|---------|
| DB init | `python -m src.cli init` |
| End-to-end | `python -m src.cli full-workflow --owner OWNER --repo REPO --output-dir docs` |
| Retrieve | `python -m src.cli retrieve "your question"` |
| Validate | `python -m src.cli validate` |

---

*Generated to document a real run against `outrigger-project/multiarch-tuning-operator`.*

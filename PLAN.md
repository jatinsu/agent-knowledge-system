# Proof-of-Concept Build Plan: Agentic Documentation Generator

This document outlines a structured, step-by-step implementation plan for the multi-agent, graph-driven documentation platform. It is formatted specifically for consumption by coding agents to ensure strict adherence to system constraints, architectural decisions, and agentic documentation guidelines.

---

## 1. System Constraints & Core Rules

Before initiating implementation, the following architectural invariants must be hardcoded into the system design:

* **Order of Operations:** Knowledge Graph (KG) creation strictly precedes Documentation Generation. Docs are derived artifacts of the KG.
* **Source of Truth:** The Knowledge Graph (stored as JSON) is the sole source of truth for reasoning and navigation.
* **Metadata Storage:** A SQL database is used exclusively for indexing metadata (PRs, Jira tickets, file paths). It must not be queried by LLMs for reasoning.
* **MCP Boundaries:** GitHub and JIRA MCP servers are strictly ingestion adapters. They must not influence graph construction or generation logic.
* **Retrieval Strictness:** All context gathering must pass through the Retrieval Agent. Direct repository file grepping by generative agents is prohibited. Graph traversal is capped at 3 hops. Context bundles must not exceed 700 lines.
* **API Management:** A centralized LLM Gateway must handle all Gemini API requests to support multiple agents using a single key.

---

## 2. Implementation Phases

### Phase 1: Ingestion & Metadata Layer

**Objective:** Fetch raw data from external sources and normalize it into a local metadata index.

* **Step 1.1: Initialize SQL Metadata Database**
    * Create schemas for: `repos`, `pull_requests`, `jira_tickets`, `features`, `documents`, and `graph_versions`.
* **Step 1.2: Implement Ingestion Adapters (MCP integration)**
    * Implement `github_ingestor` using GitHub MCP to fetch PRs, commits, repo structure, markdown, YAML, and CRDs.
    * Implement `jira_ingestor` using JIRA MCP to fetch tickets, epics, and story links.
* **Step 1.3: Data Normalization**
    * Normalize raw API responses into standard canonical objects and persist them to the SQL metadata database.

### Phase 2: Structuring & Initial Knowledge Graph

**Objective:** Correlate disparate data points into cohesive features and build the foundational JSON Knowledge Graph.

* **Step 2.1: Feature Construction**
    * Implement `jira_pr_linker` to map JIRA IDs extracted from PR metadata to JIRA tickets.
    * Implement `feature_builder` to aggregate PRs, tickets, and components into structured JSON feature objects.
* **Step 2.2: Initial Knowledge Graph Generation**
    * Initialize the JSON-based graph store (`nodes[]`, `edges[]`).
    * Create node factories for strict typing: `Concept`, `Workflow`, `ADR`, `ExecutionPlan`, `EntryPoint`, `Document`, `Section`.
    * Generate initial nodes from structured features and map their relationships using predefined edge types (`DEEP_DIVE`, `RELATED`, `DECIDED_BY`, `PLANNED_IN`, `REFERENCES`, `INDEXES`).
    * Ensure the graph can be loaded into memory for runtime traversal.

### Phase 3: Core Infrastructure & Generation Agents

**Objective:** Set up the orchestration layer and generate the agentic documentation based on the KG.

* **Step 3.1: Implement LLM Gateway**
    * Build a centralized service to manage Gemini API calls. Include rate limiting, request queueing, and agent tagging (e.g., `agent_id`, `task_type`).
* **Step 3.2: Implement Router / Orchestrator Agent**
    * Build the central controller to route tasks between ingestion, generation, retrieval, and validation modules. Enforce strict agent boundaries.
* **Step 3.3: Implement Documentation Generator Agent**
    * Inject strict prompt templates conforming to the agentic-docs-guide.
    * Implement the pipeline: Read feature context -> Generate ADR -> Generate Execution Plan -> Save to structured directory format.
    * Generate repository-level entry points: `AGENTS.md` (graph summary, entry points) and `ARCHITECTURE.md` (component graph, controller relationships).

### Phase 4: Retrieval & Validation Systems

**Objective:** Provide strict access to the graph and ensure all generated outputs meet quality and structural standards.

* **Step 4.1: Implement Retrieval Agent**
    * Build the query pipeline: Intent Classification -> Entity Extraction -> Node Resolution.
    * Implement Breadth-First Search (BFS) graph traversal strictly limited to $\le$ 3 hops.
    * Implement context assembly and compression to ensure the output bundle is under 700 lines.
* **Step 4.2: Implement Validation Agent**
    * Build the validation loop: Quality scoring, schema compliance, link integrity, and coverage calculation.
    * Implement the corrective loop mechanism: Generate -> Validate -> If invalid, re-prompt with schema constraints -> Revalidate.

### Phase 5: End-to-End Workflow & Testing

**Objective:** Connect the pipeline and establish deterministic evaluation metrics.

* **Step 5.1: Developer Workflow Integration**
    * Implement the target flow: Investigate (Retrieval Agent) -> Create Plan (Doc Gen Agent) -> Get Alignment (Validation) -> Implement -> Complete.
* **Step 5.2: Testing Suite Implementation**
    * **Unit Tests:** Verify ingestion normalization, graph builder deterministic logic, and schema validator rules.
    * **Graph Tests:** Assert 0 orphan nodes, verify $\le$ 3-hop reachability from `AGENTS.md`, and validate node/edge typing.
    * **Evaluation Tests:** Simulate developer tasks (e.g., "bug fix context") to measure token usage and verify context budget compliance. Validate minimum coverage thresholds ($\ge$ 5 concepts, $\ge$ 3 ADRs).

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Agentic Documentation Generator** - a multi-agent system that creates structured, navigable documentation from code repositories, GitHub PRs, and Jira tickets. The system uses a knowledge graph as the central source of truth, with specialized agents for ingestion, generation, retrieval, and validation.

**Status:** Greenfield project in planning phase. Implementation follows the phased approach in PLAN.md.

## Architectural Invariants

These constraints are **non-negotiable** and must be enforced in all code:

### Order of Operations
Knowledge Graph (KG) creation **strictly precedes** Documentation Generation. Docs are derived artifacts of the KG, never the other way around.

### Source of Truth Hierarchy
1. **Knowledge Graph (JSON)** - Sole source of truth for reasoning and navigation
2. **SQL Metadata Database** - Indexing only (PRs, Jira tickets, file paths). LLMs must not query this for reasoning.
3. **MCP Servers (GitHub, JIRA)** - Ingestion adapters only. Must not influence graph construction or generation logic.

### Agent Boundaries

**Retrieval Agent** - The only agent allowed to gather context from the codebase
- All context gathering must pass through this agent
- Direct repository file grepping by generative agents is **prohibited**
- Graph traversal capped at **3 hops maximum**
- Context bundles must not exceed **700 lines**

**Router/Orchestrator Agent** - Central controller that routes tasks between modules
- Enforces strict boundaries between ingestion, generation, retrieval, and validation

**Documentation Generator Agent** - Creates structured docs from KG nodes
- Must follow agentic-docs-guide templates
- Pipeline: Read feature context → Generate ADR → Generate Execution Plan → Save

**Validation Agent** - Ensures output quality and structural compliance
- Implements corrective loop: Generate → Validate → Re-prompt if invalid → Revalidate

### API Management
A centralized **LLM Gateway** handles all Gemini API requests. This enables multiple agents to share a single API key with rate limiting, request queueing, and agent tagging.

## System Architecture

### Data Flow
```
External Sources (GitHub/Jira)
  ↓ [MCP Adapters]
SQL Metadata DB (normalized)
  ↓ [Feature Builder]
Knowledge Graph (JSON)
  ↓ [Doc Generator + Retrieval Agent]
Structured Documentation
  ↓ [Validation Agent]
Validated Output
```

### Knowledge Graph Structure

**Storage:** JSON-based graph with `nodes[]` and `edges[]` arrays, loadable into memory for runtime traversal.

**Node Types:**
- `Concept` - Core abstractions and domain models
- `Workflow` - Process flows and interaction patterns
- `ADR` - Architectural Decision Records
- `ExecutionPlan` - Implementation plans
- `EntryPoint` - Navigation starting points
- `Document` - Generated documentation artifacts
- `Section` - Document subsections

**Edge Types:**
- `DEEP_DIVE` - Links overview to detailed explanation
- `RELATED` - Associates related concepts
- `DECIDED_BY` - Links implementation to decision rationale
- `PLANNED_IN` - Connects code to execution plan
- `REFERENCES` - General reference relationship
- `INDEXES` - Entry point to content mapping

**Graph Constraints:**
- Zero orphan nodes allowed
- All nodes must be reachable within ≤3 hops from `AGENTS.md`
- Strict node/edge typing enforced

## Implementation Phases

Follow these phases **in order**. Each phase has hard dependencies on previous phases.

### Phase 1: Ingestion & Metadata Layer
Initialize SQL schemas (`repos`, `pull_requests`, `jira_tickets`, `features`, `documents`, `graph_versions`). Build MCP-based ingestors for GitHub and Jira. Normalize and persist to SQL.

### Phase 2: Structuring & Initial Knowledge Graph
Implement `jira_pr_linker` and `feature_builder`. Initialize JSON graph store with typed node factories. Generate initial nodes from features and establish relationships.

### Phase 3: Core Infrastructure & Generation Agents
Build LLM Gateway. Implement Router/Orchestrator. Build Documentation Generator with strict template adherence. Generate repository-level entry points (`AGENTS.md`, `ARCHITECTURE.md`).

### Phase 4: Retrieval & Validation Systems
Build Retrieval Agent with BFS traversal (≤3 hops, ≤700 lines). Implement Validation Agent with quality scoring, schema compliance, and corrective loops.

### Phase 5: End-to-End Workflow & Testing
Connect the pipeline. Build test suite covering:
- **Unit Tests:** Ingestion normalization, graph builder determinism, schema validation
- **Graph Tests:** Orphan detection, reachability validation, typing enforcement
- **Evaluation Tests:** Token usage, context budget compliance, coverage thresholds (≥5 concepts, ≥3 ADRs)

## Key Implementation Notes

### When Building the Knowledge Graph
- Features are aggregated from PRs + Jira tickets + code components
- Graph must be serializable as JSON for persistence and runtime loading
- All graph mutations must preserve reachability and typing invariants

### When Implementing Agents
- Each agent must communicate through the Router/Orchestrator
- All LLM calls must go through the centralized Gateway
- Retrieval Agent is the **only** code access point for generative agents

### Developer Workflow Target
The system should support: Investigate (Retrieval) → Create Plan (Doc Gen) → Get Alignment (Validation) → Implement → Complete

## Repository Structure (Planned)

Once implemented, expect:
```
/ingestors/          # MCP adapters for GitHub, Jira
/graph/              # KG construction and traversal logic
/agents/             # Router, Generator, Retrieval, Validation
/gateway/            # Centralized LLM API management
/db/                 # SQL metadata schemas and migrations
/docs/               # Generated documentation output
/tests/              # Unit, graph, and evaluation tests
```

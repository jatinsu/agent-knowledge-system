# Agent Knowledge System

A multi-agent system that generates structured, navigable documentation from code repositories, GitHub PRs, and Jira tickets using a knowledge graph as the central source of truth.

## Features

- **Knowledge Graph Architecture**: JSON-based graph with typed nodes (Concepts, ADRs, Execution Plans) and relationships
- **Multi-Agent System**: Specialized agents for ingestion, generation, retrieval, and validation
- **Strict Constraints**: 3-hop graph traversal, 700-line context limits, retrieval-only code access
- **LLM Gateway**: Centralized Gemini API management with rate limiting and request tracking
- **Comprehensive Testing**: Unit, graph validation, and evaluation test suites

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd agent-knowledge-system-gemini

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Initialize Database

```bash
python -m src.cli init
```

### Run Full Workflow

```bash
python -m src.cli full-workflow --owner OWNER --repo REPO --output-dir docs
```

## Build Commands

```bash
# Install all dependencies
make install

# Run all tests
make test

# Run specific test suites
make test-unit       # Unit tests
make test-graph      # Graph validation tests
make test-eval       # Evaluation tests

# Lint code
make lint

# Format code
make format

# Full build (format + lint + test)
make build

# Clean artifacts
make clean
```

## CLI Commands

### Ingestion

```bash
# Ingest GitHub PRs
python -m src.cli ingest-github --owner OWNER --repo REPO --limit 100

# Ingest Jira tickets by JQL
python -m src.cli ingest-jira --jql "project = PROJ" --limit 50

# Ingest Jira tickets by keys
python -m src.cli ingest-jira --keys "PROJ-123,PROJ-456"
```

### Feature Building

```bash
# Build features from ingested data
python -m src.cli build-features --repo-id 1
```

### Knowledge Graph

```bash
# Build knowledge graph
python -m src.cli build-graph --repo-id 1

# Validate graph
python -m src.cli validate
```

### Documentation Generation

```bash
# Generate documentation
python -m src.cli generate-docs --output-dir docs
```

### Retrieval

```bash
# Retrieve context from knowledge graph
python -m src.cli retrieve "How does authentication work?"
```

## Architecture

### Data Flow

```
GitHub/Jira (MCP) → SQL Metadata → Features → Knowledge Graph → Documentation → Validation
```

### Key Components

- **Ingestors** (`src/ingestors/`): GitHub and Jira MCP adapters
- **Graph** (`src/graph/`): Knowledge graph types, builders, storage
- **Gateway** (`src/gateway/`): Centralized LLM API management
- **Agents** (`src/agents/`): Router, Generator, Retrieval, Validation
- **Database** (`src/db/`): SQL metadata models

### Architectural Constraints

1. **Knowledge Graph First**: Graph creation precedes documentation generation
2. **Single Source of Truth**: Knowledge Graph (JSON) is authoritative
3. **Retrieval Agent Boundary**: Only agent allowed to access codebase
4. **3-Hop Limit**: Graph traversal capped at 3 hops maximum
5. **700-Line Context**: Context bundles limited to 700 lines
6. **Centralized API**: All LLM calls through gateway

## Testing

### Test Coverage

- **Unit Tests** (12 tests): Graph operations, ingestor utilities
- **Graph Tests** (4 tests): Orphan detection, reachability, typing
- **Evaluation Tests** (3 tests): Coverage thresholds, context limits, token usage

```bash
# Run with coverage report
pytest src/tests/ -v --cov=src --cov-report=html

# View coverage
open htmlcov/index.html
```

## Configuration

Edit `.env` file:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key

# Optional
GEMINI_MODEL=gemini-2.0-flash
DATABASE_URL=sqlite:///./knowledge_system.db
MAX_GRAPH_HOPS=3
MAX_CONTEXT_LINES=700
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# For GitHub ingestion
GITHUB_TOKEN=your_github_token

# For Jira ingestion
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your_email@example.com
JIRA_API_TOKEN=your_jira_token
```

## Development

### Project Structure

```
src/
├── agents/          # Agent implementations
├── db/              # Database models
├── gateway/         # LLM API gateway
├── graph/           # Knowledge graph
├── ingestors/       # Data ingestion
├── templates/       # Doc templates
├── tests/           # Test suites
├── cli.py           # CLI interface
└── config.py        # Configuration
```

### Adding New Agents

1. Create agent in `src/agents/`
2. Register with Router in `src/agents/router.py`
3. Add TaskType enum value
4. Implement execute method
5. Add tests in `src/tests/`

## License

MIT
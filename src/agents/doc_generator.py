from pathlib import Path
from typing import Any

from src.gateway.llm_gateway import LLMGateway
from src.graph.types import KnowledgeGraph, Node, NodeType
from src.templates.adr_template import (
    ADR_TEMPLATE,
    EXECUTION_PLAN_TEMPLATE,
    AGENTS_MD_TEMPLATE,
    ARCHITECTURE_MD_TEMPLATE,
)


class DocumentationGenerator:
    def __init__(self, llm_gateway: LLMGateway):
        self.gateway = llm_gateway
        self.agent_id = "doc_generator"

    async def generate_adr(self, feature_context: dict[str, Any]) -> str:
        system_prompt = """You are a technical writer creating Architectural Decision Records (ADRs).
Follow the agentic documentation guide principles:
- Focus on WHY decisions were made, not just WHAT was implemented
- Include context about constraints and tradeoffs
- Link to related concepts and execution plans
- Be concise but comprehensive"""

        user_prompt = f"""Create an ADR for the following feature:

Feature: {feature_context['name']}
Description: {feature_context.get('description', 'N/A')}
Components: {feature_context.get('components', 'N/A')}
PRs: {feature_context.get('pr_count', 0)}
Jira Tickets: {feature_context.get('jira_count', 0)}

Generate a complete ADR following the template structure."""

        content = await self.gateway.generate(
            f"{system_prompt}\n\n{user_prompt}",
            agent_id=self.agent_id,
            task_type="adr_generation",
            temperature=0.5,
        )

        return content

    async def generate_execution_plan(self, feature_context: dict[str, Any]) -> str:
        system_prompt = """You are creating an Execution Plan for implementing a feature.
Focus on:
- Clear step-by-step instructions
- Prerequisites and dependencies
- Acceptance criteria
- Rollback strategy"""

        user_prompt = f"""Create an Execution Plan for:

Feature: {feature_context['name']}
Description: {feature_context.get('description', 'N/A')}
Components: {feature_context.get('components', 'N/A')}

Generate a complete execution plan."""

        content = await self.gateway.generate(
            f"{system_prompt}\n\n{user_prompt}",
            agent_id=self.agent_id,
            task_type="plan_generation",
            temperature=0.5,
        )

        return content

    async def generate_agents_md(self, graph: KnowledgeGraph, output_path: Path) -> Path:
        concept_nodes = [n for n in graph.nodes if n.type == NodeType.CONCEPT]
        adr_nodes = [n for n in graph.nodes if n.type == NodeType.ADR]
        plan_nodes = [n for n in graph.nodes if n.type == NodeType.EXECUTION_PLAN]

        features_list = "\n".join([f"- {n.title}" for n in concept_nodes[:10]])
        navigation = "Use the knowledge graph to explore relationships between concepts, decisions, and plans."

        content = AGENTS_MD_TEMPLATE.format(
            overview="This repository contains documentation generated from code, PRs, and Jira tickets.",
            features=features_list,
            navigation=navigation,
            concept_count=len(concept_nodes),
            adr_count=len(adr_nodes),
            plan_count=len(plan_nodes),
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        return output_path

    async def generate_architecture_md(self, graph: KnowledgeGraph, output_path: Path) -> Path:
        concept_nodes = [n for n in graph.nodes if n.type == NodeType.CONCEPT]
        workflow_nodes = [n for n in graph.nodes if n.type == NodeType.WORKFLOW]

        components = "\n".join([f"- {n.title}" for n in concept_nodes[:10]])
        workflows = "\n".join([f"- {n.title}" for n in workflow_nodes[:5]])

        content = ARCHITECTURE_MD_TEMPLATE.format(
            components=components or "No components defined yet.",
            data_flow=workflows or "No workflows defined yet.",
            key_decisions="See individual ADRs for architectural decisions.",
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        return output_path

    async def generate_feature_docs(
        self, feature_context: dict[str, Any], output_dir: Path
    ) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)

        adr_content = await self.generate_adr(feature_context)
        adr_path = output_dir / f"adr_{feature_context['name'].replace(' ', '_').lower()}.md"
        adr_path.write_text(adr_content)

        plan_content = await self.generate_execution_plan(feature_context)
        plan_path = output_dir / f"plan_{feature_context['name'].replace(' ', '_').lower()}.md"
        plan_path.write_text(plan_content)

        return {"adr": adr_path, "plan": plan_path}

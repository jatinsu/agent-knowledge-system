from typing import Any
from pathlib import Path

from src.gateway.llm_gateway import LLMGateway
from src.graph.types import KnowledgeGraph, NodeType


class ValidationAgent:
    def __init__(self, llm_gateway: LLMGateway):
        self.gateway = llm_gateway
        self.agent_id = "validation_agent"

    async def score_quality(self, content: str, doc_type: str) -> dict[str, Any]:
        system_prompt = f"""Rate the quality of this {doc_type} on these dimensions (0-10):
- Clarity: How clear and understandable is the content?
- Completeness: Does it cover all necessary aspects?
- Structure: Is it well-organized and follows best practices?
- Actionability: For execution plans, is it actionable? For ADRs, does it explain the WHY?

Return JSON with scores:
{{"clarity": X, "completeness": X, "structure": X, "actionability": X, "overall": X}}"""

        user_prompt = f"Content to rate:\n\n{content[:2000]}"

        response = await self.gateway.generate(
            f"{system_prompt}\n\n{user_prompt}",
            agent_id=self.agent_id,
            task_type="quality_scoring",
            temperature=0.3,
        )

        try:
            import json

            scores = json.loads(response)
            return scores
        except Exception:
            return {
                "clarity": 5,
                "completeness": 5,
                "structure": 5,
                "actionability": 5,
                "overall": 5,
            }

    def validate_schema(self, content: str, doc_type: str) -> dict[str, Any]:
        required_sections = {
            "adr": ["Status", "Context", "Decision", "Consequences"],
            "plan": ["Goal", "Prerequisites", "Steps", "Acceptance Criteria"],
        }

        if doc_type.lower() not in required_sections:
            return {"valid": True, "missing_sections": []}

        missing = []
        for section in required_sections[doc_type.lower()]:
            if section not in content:
                missing.append(section)

        return {"valid": len(missing) == 0, "missing_sections": missing}

    def validate_graph(self, graph: KnowledgeGraph) -> dict[str, Any]:
        validation_result = graph.validate_graph()

        concept_count = len([n for n in graph.nodes if n.type == NodeType.CONCEPT])
        adr_count = len([n for n in graph.nodes if n.type == NodeType.ADR])
        plan_count = len([n for n in graph.nodes if n.type == NodeType.EXECUTION_PLAN])

        coverage = {
            "concepts": concept_count,
            "adrs": adr_count,
            "plans": plan_count,
            "meets_minimum": concept_count >= 5 and adr_count >= 3,
        }

        return {
            "graph_valid": validation_result["valid"],
            "orphan_nodes": validation_result["orphan_nodes"],
            "dangling_edges": validation_result["dangling_edges"],
            "node_count": validation_result["node_count"],
            "edge_count": validation_result["edge_count"],
            "coverage": coverage,
        }

    async def validate_document(
        self, file_path: Path, doc_type: str, min_quality_score: float = 6.0
    ) -> dict[str, Any]:
        content = file_path.read_text()

        schema_validation = self.validate_schema(content, doc_type)
        quality_scores = await self.score_quality(content, doc_type)

        is_valid = (
            schema_validation["valid"]
            and quality_scores.get("overall", 0) >= min_quality_score
        )

        return {
            "valid": is_valid,
            "schema_validation": schema_validation,
            "quality_scores": quality_scores,
            "file_path": str(file_path),
        }

    async def corrective_loop(
        self,
        content: str,
        doc_type: str,
        max_iterations: int = 3,
    ) -> tuple[str, dict[str, Any]]:
        current_content = content
        iteration = 0

        while iteration < max_iterations:
            validation = await self.validate_document(
                Path("/tmp/temp_doc.md"), doc_type, min_quality_score=7.0
            )

            if validation["valid"]:
                return current_content, validation

            system_prompt = f"""The following {doc_type} failed validation.
Issues:
- Missing sections: {validation['schema_validation']['missing_sections']}
- Quality scores: {validation['quality_scores']}

Regenerate the content to address these issues while maintaining the core information."""

            current_content = await self.gateway.generate(
                f"{system_prompt}\n\nOriginal content:\n{current_content}",
                agent_id=self.agent_id,
                task_type="corrective_regeneration",
                temperature=0.5,
            )

            iteration += 1

        final_validation = await self.validate_document(
            Path("/tmp/temp_doc.md"), doc_type, min_quality_score=7.0
        )
        return current_content, final_validation

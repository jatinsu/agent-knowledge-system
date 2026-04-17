ADR_TEMPLATE = """# Architectural Decision Record: {title}

## Status
{status}

## Context
{context}

## Decision
{decision}

## Consequences
{consequences}

## Related
{related}
"""

EXECUTION_PLAN_TEMPLATE = """# Execution Plan: {title}

## Goal
{goal}

## Prerequisites
{prerequisites}

## Steps
{steps}

## Acceptance Criteria
{acceptance_criteria}

## Rollback Plan
{rollback_plan}
"""

AGENTS_MD_TEMPLATE = """# AGENTS.md

Repository Knowledge Graph Entry Point

## Overview
{overview}

## Features
{features}

## Navigation
{navigation}

## Graph Statistics
- Total Concepts: {concept_count}
- Total ADRs: {adr_count}
- Total Execution Plans: {plan_count}
"""

ARCHITECTURE_MD_TEMPLATE = """# ARCHITECTURE.md

System Architecture Overview

## Components
{components}

## Data Flow
{data_flow}

## Key Decisions
{key_decisions}
"""

# 20251212_120944-adr-system-implementation

## Status

Accepted

## Context

The project needed a structured approach to capture architectural decisions, support planning, and maintain institutional knowledge as the codebase evolves. Without a system, decisions were scattered across commits and lost over time.

**Source commits:**

- 0042f6d: Add: Introduce ADR agents for decision support, planning, execution, research, and skill creation

## Decision

Implemented a multi-agent ADR (Architecture Decision Record) system with specialized agents for different phases of the development workflow:

- **Decision Support Agent**: Gathers context from ADRs, skills, and past work before planning
- **Planner Agent**: Creates line-precise implementation plans from research
- **Executor Agent**: Implements approved plans with fresh context
- **Research Agent**: Explores codebase and generates compressed findings
- **Skill Creator Agent**: Extracts reusable patterns into skills

The system uses a workflow of: Context → Research → Plan → Execute → Review, with human review gates at critical points.

## Consequences

### Positive

- Captures architectural decisions as they happen
- Provides automated context retrieval for new work
- Creates reusable procedural expertise via skills
- Enforces review gates to prevent drift from constraints

### Negative

- Additional overhead for small changes
- Requires team adoption and discipline
- Agents consume context tokens

### Constraints

- Plans must be approved before execution
- Executor receives ONLY the plan (fresh context)
- Stay under 40% context utilization ("smart zone")
- Use `/adr-compact` when stuck 3+ times

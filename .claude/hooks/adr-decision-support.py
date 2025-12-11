#!/usr/bin/env python3
"""
UserPromptSubmit Hook: Decision Support Context Injection

Automatically searches for relevant ADRs, skills, and past work
when prompts contain planning/feature keywords.

Exit codes:
- 0: Success (with or without context injection)
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime


# Keywords that trigger context gathering
TRIGGER_KEYWORDS = [
    "/adr-feature",
    "/adr-research",
    "implement",
    "build",
    "create",
    "add feature",
    "add new",
    "plan",
    "design",
    "refactor",
]

# Common words to filter out from keyword extraction
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "to", "of",
    "in", "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "under",
    "again", "further", "then", "once", "add", "create", "make", "build",
    "implement", "feature", "new", "please", "help", "want", "like", "need",
    "think", "know", "use", "using", "this", "that", "these", "those",
}


def should_trigger(prompt: str) -> bool:
    """Check if prompt contains trigger keywords."""
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in TRIGGER_KEYWORDS)


def extract_keywords(prompt: str) -> list[str]:
    """Extract meaningful keywords from prompt."""
    words = re.findall(r"\b\w+\b", prompt.lower())
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    return list(set(keywords))[:10]  # Top 10 unique keywords


def search_adrs(keywords: list[str], base_path: Path) -> list[dict]:
    """Search ADR decisions for relevant content."""
    adr_path = base_path / "adr" / "decisions"
    if not adr_path.exists():
        return []

    relevant = []
    for adr_file in adr_path.glob("*.md"):
        try:
            content = adr_file.read_text().lower()
            matches = sum(1 for kw in keywords if kw in content)
            if matches > 0:
                # Extract title from filename
                name = adr_file.stem
                title = name.split("-", 1)[1] if "-" in name else name
                title = title.replace("-", " ").title()

                # Try to extract status
                status = "Unknown"
                if "status" in content:
                    if "accepted" in content:
                        status = "Accepted"
                    elif "proposed" in content:
                        status = "Proposed"
                    elif "deprecated" in content:
                        status = "Deprecated"

                relevant.append({
                    "file": str(adr_file.relative_to(base_path)),
                    "title": title,
                    "status": status,
                    "matches": matches,
                })
        except Exception:
            continue

    # Sort by relevance (number of keyword matches)
    relevant.sort(key=lambda x: x["matches"], reverse=True)
    return relevant[:3]  # Top 3


def search_skills(keywords: list[str], base_path: Path) -> list[str]:
    """Find applicable skills."""
    skills_path = base_path / "skills"
    if not skills_path.exists():
        return []

    relevant = []
    for skill_dir in skills_path.iterdir():
        if skill_dir.is_dir() and skill_dir.name.startswith("adr-"):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                try:
                    content = skill_file.read_text().lower()
                    if any(kw in content for kw in keywords):
                        relevant.append(skill_dir.name)
                except Exception:
                    continue

    return relevant[:3]  # Top 3


def search_past_tasks(keywords: list[str], base_path: Path) -> list[dict]:
    """Find similar past work."""
    tasks_path = base_path / "adr" / "tasks"
    if not tasks_path.exists():
        return []

    relevant = []
    for task_dir in tasks_path.iterdir():
        if task_dir.is_dir():
            research_file = task_dir / "research.md"
            if research_file.exists():
                try:
                    content = research_file.read_text().lower()
                    matches = sum(1 for kw in keywords if kw in content)
                    if matches > 0:
                        relevant.append({
                            "task": task_dir.name,
                            "file": str(research_file.relative_to(base_path)),
                            "matches": matches,
                        })
                except Exception:
                    continue

    relevant.sort(key=lambda x: x["matches"], reverse=True)
    return relevant[:2]  # Top 2


def extract_constraints(adrs: list[dict], base_path: Path) -> list[str]:
    """Extract constraint statements from ADRs."""
    constraints = []
    constraint_patterns = [
        r"never\s+([^.]+)",
        r"always\s+([^.]+)",
        r"must\s+([^.]+)",
        r"must not\s+([^.]+)",
        r"required[:\s]+([^.]+)",
    ]

    for adr in adrs[:2]:  # Only check top 2 ADRs for constraints
        adr_file = base_path / adr["file"]
        if adr_file.exists():
            try:
                content = adr_file.read_text()
                for pattern in constraint_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches[:2]:  # Max 2 per pattern
                        constraint = match.strip()
                        if len(constraint) > 10 and len(constraint) < 100:
                            constraints.append(f"{constraint} (`{adr['file']}`)")
            except Exception:
                continue

    return constraints[:3]  # Max 3 constraints


def build_context(
    adrs: list[dict],
    skills: list[str],
    tasks: list[dict],
    constraints: list[str],
) -> str:
    """Build the context injection string."""
    if not (adrs or skills or tasks or constraints):
        return ""

    parts = [
        "\n---",
        "**Decision Context** (auto-gathered):\n",
    ]

    if constraints:
        parts.append("**Constraints:**")
        for c in constraints:
            parts.append(f"  - {c}")
        parts.append("")

    if adrs:
        parts.append("**Relevant ADRs:**")
        for adr in adrs:
            parts.append(f"  - `{adr['file']}` ({adr['status']})")
        parts.append("")

    if skills:
        parts.append("**Applicable Skills:**")
        for skill in skills:
            parts.append(f"  - `{skill}`")
        parts.append("")

    if tasks:
        parts.append("**Similar Past Work:**")
        for task in tasks:
            parts.append(f"  - `{task['file']}`")
        parts.append("")

    parts.append("---\n")

    return "\n".join(parts)


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    prompt = data.get("prompt", "")

    # Only process if trigger keywords detected
    if not should_trigger(prompt):
        sys.exit(0)

    # Determine base path (project directory)
    base_path = Path.cwd()

    # Extract keywords from prompt
    keywords = extract_keywords(prompt)
    if not keywords:
        sys.exit(0)

    # Gather context
    adrs = search_adrs(keywords, base_path)
    skills = search_skills(keywords, base_path)
    tasks = search_past_tasks(keywords, base_path)
    constraints = extract_constraints(adrs, base_path) if adrs else []

    # Build context string
    context = build_context(adrs, skills, tasks, constraints)

    if context:
        print(json.dumps({"additionalContext": context}))

    sys.exit(0)


if __name__ == "__main__":
    main()

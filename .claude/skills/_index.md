# ADR Skills Index

> Skills provide procedural expertise. Load only what you need.

## Available Skills

| Skill                   | Description                                                         | Location                                |
| ----------------------- | ------------------------------------------------------------------- | --------------------------------------- |
| `adr-research-codebase` | Explore AE-Scientist codebase efficiently (TypeScript, Python, MDX) | `.claude/skills/adr-research-codebase/` |
| `adr-create-feature`    | Standard feature implementation workflow                            | `.claude/skills/adr-create-feature/`    |
| `adr-write-tests`       | Testing patterns for this project                                   | `.claude/skills/adr-write-tests/`       |

## Usage

To activate a skill, read its SKILL.md:

```
Read .claude/skills/adr-{skill-name}/SKILL.md
```

Skills may have supporting files (patterns.md, scripts) — load only if needed.

## Adding Skills

Use `/adr-save-skill {name}` to create new skills from successful patterns.

## Progressive Disclosure

- **This index**: Always available (~100 tokens)
- **SKILL.md**: Loaded when activated (~500 tokens each)
- **Supporting files**: Loaded on-demand

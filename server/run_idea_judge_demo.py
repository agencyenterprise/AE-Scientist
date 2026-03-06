"""
End-to-end demo: generate ideas from all markdown files in ideas/, then judge and refine each.

Usage (from the server/ directory):
    uv run run_idea_judge_demo.py

The script:
  1. Discovers all ideas/idea_*.md files
  2. For each file: generates a structured idea via LLM, then runs the judge
  3. If the judge says "revise" or "reject", runs the refiner to produce an improved version
  4. Saves per-file JSON results to judge-output/<idea_name>.json
  5. Prints a summary table at the end

Provider defaults to openai / gpt-5.4. Override with env vars:
    JUDGE_PROVIDER=anthropic JUDGE_MODEL=claude-sonnet-4-5 uv run run_idea_judge_demo.py
    JUDGE_PROVIDER=openai    JUDGE_MODEL=gpt-5.4           uv run run_idea_judge_demo.py
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent  # AE-Scientist/
SERVER_DIR = Path(__file__).parent  # AE-Scientist/server/
IDEAS_DIR = REPO_ROOT / "ideas"
OUTPUT_DIR = REPO_ROOT / "judge-output"
ENV_FILE = REPO_ROOT / "research_pipeline" / ".env"

sys.path.insert(0, str(SERVER_DIR))

# ---------------------------------------------------------------------------
# Load .env from research_pipeline/
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv

    load_dotenv(ENV_FILE)
    print(f"Loaded .env from {ENV_FILE}")
except ImportError:
    print("python-dotenv not available; using shell environment only")

# ---------------------------------------------------------------------------
# Stub every app.config required variable that the judge/idea-gen doesn't need
# ---------------------------------------------------------------------------
_STUBS: dict[str, str] = {
    "DATABASE_URL": "postgresql://stub:stub@localhost/stub",
    "DB_POOL_MIN_CONN": "1",
    "DB_POOL_MAX_CONN": "2",
    "CLERK_SECRET_KEY": "stub",
    "CLERK_PUBLISHABLE_KEY": "stub",
    "XAI_API_KEY": os.environ.get("XAI_API_KEY", "stub"),
    "RUNPOD_API_KEY": "stub",
    "RUNPOD_SSH_ACCESS_KEY": "stub",
    "RUNPOD_SUPPORTED_GPUS": "[]",
    "AWS_ACCESS_KEY_ID": "stub",
    "AWS_SECRET_ACCESS_KEY": "stub",
    "AWS_REGION": "us-east-1",
    "AWS_S3_BUCKET_NAME": "stub",
    "STRIPE_SECRET_KEY": "stub",
    "STRIPE_WEBHOOK_SECRET": "stub",
    "STRIPE_CHECKOUT_SUCCESS_URL": "http://localhost",
    "STRIPE_PRICE_IDS": "price_stub",
    "MIN_BALANCE_CENTS_FOR_RESEARCH_PIPELINE": "5000",
    "MIN_BALANCE_CENTS_FOR_CHAT_MESSAGE": "10",
    "MIN_BALANCE_CENTS_FOR_PAPER_REVIEW": "100",
    "JSON_MODEL_PRICE_PER_MILLION_IN_CENTS": json.dumps(
        {
            "openai": {
                "gpt-4o-mini": {"input": 15, "output": 60, "cached_input": 8},
                "gpt-4o": {"input": 250, "output": 1000, "cached_input": 125},
                "gpt-4o-mini-search-preview": {"input": 25, "output": 100, "cached_input": 12},
                "gpt-4o-search-preview": {"input": 250, "output": 1000, "cached_input": 125},
            },
            "anthropic": {
                "claude-haiku-4-5": {"input": 80, "output": 400, "cached_input": 8},
                "claude-sonnet-4-5": {"input": 300, "output": 1500, "cached_input": 30},
            },
        }
    ),
    "TELEMETRY_WEBHOOK_URL": "http://localhost/stub",
    "HF_TOKEN": "stub",
    "PIPELINE_MONITOR_INTERVAL_SECONDS": "60",
    "PIPELINE_MAX_RESTART_ATTEMPTS": "3",
    "DB_POOL_USAGE_WARN_THRESHOLD": "0.8",
    "PIPELINE_MONITOR_POLL_INTERVAL_SECONDS": "30",
    "PIPELINE_MONITOR_HEARTBEAT_TIMEOUT_SECONDS": "120",
    "PIPELINE_MONITOR_MAX_MISSED_HEARTBEATS": "3",
    "PIPELINE_MONITOR_STARTUP_GRACE_SECONDS": "60",
    "PIPELINE_MONITOR_MAX_RUNTIME_HOURS": "24",
    "SERVER_AUTO_RELOAD": "false",
    "LOG_LEVEL": "INFO",
    "FRONTEND_URL": "http://localhost:3000",
    "CORS_ORIGINS": "http://localhost:3000",
    "CORS_CREDENTIALS": "true",
    "SKIP_DB_CONNECTION": "true",
    "REDIS_URL": "redis://localhost:6379",
}
for _k, _v in _STUBS.items():
    os.environ.setdefault(_k, _v)

# ---------------------------------------------------------------------------
# Mock playwright before any app imports — it's only needed by the scraper,
# not by the idea judge or idea generation flow.
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock as _MagicMock

for _mod in [
    "playwright",
    "playwright.async_api",
    "playwright.sync_api",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _MagicMock()  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Patch ae_paper_review: the local package is missing newer symbols that the
# server's paper-review feature needs.  Add lightweight stubs so imports
# succeed — these symbols are never touched by the idea judge flow.
# ---------------------------------------------------------------------------
import ae_paper_review as _apr  # noqa: E402
from enum import Enum as _Enum


def _stub_class(name: str, base=object):
    """Return a trivial stub class and register it on the ae_paper_review module."""
    cls = type(name, (base,), {})
    setattr(_apr, name, cls)
    return cls


if not hasattr(_apr, "Conference"):

    class _Conference(str, _Enum):
        NEURIPS = "neurips"
        ICLR = "iclr"
        ICML = "icml"

    _apr.Conference = _Conference  # type: ignore[attr-defined]

for _sym in [
    "BaselineReviewModel",
    "BaselineNeurIPSReviewModel",
    "BaselineICLRReviewModel",
    "BaselineICMLReviewModel",
    "ReviewModel",
    "NeurIPSReviewModel",
    "ICLRReviewModel",
    "ICMLReviewModel",
    "TokenUsageSummary",
]:
    if not hasattr(_apr, _sym):
        _stub_class(_sym)

if not hasattr(_apr, "perform_baseline_review"):

    def _perform_baseline_review(*a, **kw):
        raise NotImplementedError("perform_baseline_review is a stub")

    _apr.perform_baseline_review = _perform_baseline_review  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# App imports — safe after stubs
# ---------------------------------------------------------------------------
from app.services.idea_judge_service import JUDGE_DEFAULT_MODEL, IdeaJudgeService, IdeaJudgeResult  # noqa: E402
from app.services.idea_refiner_service import REFINER_DEFAULT_MODEL, IdeaRefinerService, IdeaRefinerResult  # noqa: E402
from app.services.langchain_llm_service import IdeaGenerationOutput  # noqa: E402
from app.services.prompts.functions import get_default_idea_generation_prompt  # noqa: E402
from app.services.prompts.render import render_text  # noqa: E402
from app.services.openai_service import OpenAIService  # noqa: E402
from app.services.anthropic_service import AnthropicService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
log = logging.getLogger(__name__)

SEP = "=" * 70
DASH = "-" * 70


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_service(provider: str):
    if provider == "anthropic":
        return AnthropicService()
    return OpenAIService()


def _print_list(label: str, items: list) -> None:
    if items:
        print(f"  {label}:")
        for item in items:
            print(f"    • {item}")


def _print_judge_report(result: IdeaJudgeResult) -> None:
    print(f"\n{SEP}")
    print(f"  JUDGE REPORT")
    print(SEP)
    print(f"  {result.summary}")
    print(SEP)

    criteria = [
        ("RELEVANCE", result.relevance),
        ("FEASIBILITY", result.feasibility),
        ("NOVELTY", result.novelty),
        ("IMPACT", result.impact),
    ]

    for name, criterion in criteria:
        d = criterion.model_dump()
        print(f"\n{'─'*70}")
        print(f"  [{name}]  score = {d['score']}/5")
        print(f"{'─'*70}")
        print(f"  {d['rationale']}")

        # Criterion-specific structured fields
        for field, label in [
            ("connection_points", "Connection points"),
            ("drift_concerns", "Drift concerns"),
            ("compute_viable", "Compute viable"),
            ("agent_implementable", "Agent implementable"),
            ("estimated_cost", "Estimated cost"),
            ("blockers", "Blockers"),
            ("core_claims", "Core claims"),
            ("related_prior_work", "Related prior work"),
            ("differentiation", "Differentiation"),
            ("novelty_risks", "Novelty risks"),
            ("research_question", "Research question"),
            ("what_changes_if_success", "What changes if success"),
            ("threat_model_assessment", "Threat model"),
            ("goodhart_risk_assessment", "Goodhart risk"),
            ("suggestions", "Suggestions"),
        ]:
            val = d.get(field)
            if val is None:
                continue
            if isinstance(val, list):
                _print_list(label, val)
            elif isinstance(val, bool):
                print(f"  {label}: {val}")
            elif val:
                print(f"  {label}: {val}")

    # Revision plan
    print(f"\n{'─'*70}")
    print(f"  [REVISION PLAN]")
    print(f"{'─'*70}")
    print(f"  {result.revision.overall_assessment}")
    print()
    for i, item in enumerate(result.revision.action_items, 1):
        priority_tag = item.priority.upper()
        print(f"  {i}. [{priority_tag}] {item.action}")
        print(f"     Addresses: {item.addresses}")

    print(f"\n{SEP}")
    print(f"  Recommendation : {result.recommendation.upper().replace('_', ' ')}")
    print(f"  Overall score  : {result.overall_score:.2f} / 5.0")
    print(
        f"  Scores         : "
        f"Relevance {result.relevance.score} | "
        f"Feasibility {result.feasibility.score} | "
        f"Novelty {result.novelty.score} | "
        f"Impact {result.impact.score}"
    )
    print(SEP)


def _print_refiner_report(result: IdeaRefinerResult) -> None:
    print(f"\n{SEP}")
    print(f"  REFINER REPORT")
    print(SEP)
    print(f"  Original : {result.original_title}  (score {result.original_overall_score:.1f}/5, {result.original_recommendation})")
    print(f"  Refined  : {result.refined_title}")
    print(f"\n  Strategy: {result.refinement_summary}")

    print(f"\n{'─'*70}")
    print(f"  CHANGES MADE ({len(result.changes_made)})")
    print(f"{'─'*70}")
    for i, change in enumerate(result.changes_made, 1):
        print(f"  {i}. {change.change}")
        print(f"     Addresses: {change.criterion_addressed}")
        print(f"     Expected:  {change.expected_score_impact}")

    print(f"\n{'─'*70}")
    print(f"  REFINED IDEA (first 500 chars)")
    print(f"{'─'*70}")
    preview = result.refined_markdown[:500]
    if len(result.refined_markdown) > 500:
        preview += "\n  ... (truncated)"
    for line in preview.split("\n"):
        print(f"  {line}")
    print(SEP)


# ---------------------------------------------------------------------------
# Per-idea pipeline
# ---------------------------------------------------------------------------


async def _process_idea_file(
    *,
    idea_path: Path,
    provider: str,
    gen_model: str,
    judge_model: str,
    refiner_model: str,
    llm_service,
    output_dir: Path,
) -> dict:
    """Generate an idea from a markdown file, judge it, optionally refine, save JSON, return summary."""
    stem = idea_path.stem  # e.g. "idea_trojan_llm"
    source_text = idea_path.read_text()

    print(f"\n{'━'*70}")
    print(f"  Processing: {idea_path.name}  ({len(source_text)} chars)")
    print(f"{'━'*70}")

    t0 = time.time()

    # Step 1: generate structured idea
    total_steps = 3
    print(f"  [1/{total_steps}] Generating idea via {provider}:{gen_model} ...")
    system_prompt = get_default_idea_generation_prompt()
    user_prompt = render_text(
        template_name="idea_generation_user.txt.j2",
        context={"conversation_text": source_text},
    )
    raw = await llm_service.generate_structured_output(
        llm_model=gen_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=IdeaGenerationOutput,
        max_completion_tokens=2000,
    )
    generated: IdeaGenerationOutput = raw
    print(f"  Generated: {generated.title}")

    # Step 2: judge
    print(f"  [2/{total_steps}] Judging via {judge_model} (4 criteria + revision) ...")
    judge = IdeaJudgeService(llm_service=llm_service)
    judge_result = await judge.judge(
        llm_model=judge_model,
        idea_title=generated.title,
        idea_markdown=generated.content,
        conversation_text=source_text,
    )

    _print_judge_report(judge_result)

    # Step 3: refine (if the judge says revise or reject)
    refiner_result: IdeaRefinerResult | None = None
    if judge_result.recommendation in ("revise", "reject"):
        print(f"  [3/{total_steps}] Refining via {refiner_model} (recommendation={judge_result.recommendation}) ...")
        refiner = IdeaRefinerService(llm_service=llm_service)
        refiner_result = await refiner.refine(
            llm_model=refiner_model,
            idea_title=generated.title,
            idea_markdown=generated.content,
            judge_result=judge_result,
            conversation_text=source_text,
        )
        _print_refiner_report(refiner_result)
    else:
        print(f"  [3/{total_steps}] Skipping refinement (recommendation={judge_result.recommendation})")

    elapsed = time.time() - t0

    # Save JSON
    output: dict = {
        "source_file": idea_path.name,
        "generated_title": generated.title,
        "generated_content": generated.content,
        "judge_result": judge_result.model_dump(),
        "refiner_result": refiner_result.model_dump() if refiner_result else None,
        "meta": {
            "gen_provider": provider,
            "gen_model": gen_model,
            "judge_model": judge_model,
            "refiner_model": refiner_model,
            "refined": refiner_result is not None,
            "elapsed_seconds": round(elapsed, 1),
        },
    }
    out_path = output_dir / f"{stem}.json"
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\n  Saved: {out_path.relative_to(REPO_ROOT)}")

    return {
        "file": idea_path.name,
        "title": generated.title,
        "overall": judge_result.overall_score,
        "recommendation": judge_result.recommendation,
        "relevance": judge_result.relevance.score,
        "feasibility": judge_result.feasibility.score,
        "novelty": judge_result.novelty.score,
        "impact": judge_result.impact.score,
        "refined": refiner_result is not None,
        "refined_title": refiner_result.refined_title if refiner_result else None,
        "elapsed": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    provider = os.environ.get("JUDGE_PROVIDER", "openai").lower()
    gen_model = os.environ.get("JUDGE_MODEL", JUDGE_DEFAULT_MODEL)
    judge_model = os.environ.get("JUDGE_MODEL", JUDGE_DEFAULT_MODEL)
    refiner_model = os.environ.get("REFINER_MODEL", REFINER_DEFAULT_MODEL)

    # Discover idea files
    idea_files = sorted(IDEAS_DIR.glob("idea_*.md"))
    if not idea_files:
        print(f"ERROR: no idea_*.md files found in {IDEAS_DIR}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{SEP}")
    print(f"  AE Scientist — Batch Idea Judge + Refiner Demo")
    print(f"  provider={provider}  gen_model={gen_model}  judge_model={judge_model}  refiner_model={refiner_model}")
    print(f"  ideas found: {len(idea_files)}")
    print(f"  output dir:  {OUTPUT_DIR.relative_to(REPO_ROOT)}")
    print(SEP)

    llm_service = _resolve_service(provider)
    summaries: list[dict] = []

    for idea_path in idea_files:
        try:
            summary = await _process_idea_file(
                idea_path=idea_path,
                provider=provider,
                gen_model=gen_model,
                judge_model=judge_model,
                refiner_model=refiner_model,
                llm_service=llm_service,
                output_dir=OUTPUT_DIR,
            )
            summaries.append(summary)
        except Exception:
            log.exception("Failed to process %s", idea_path.name)
            summaries.append({
                "file": idea_path.name,
                "title": "ERROR",
                "overall": 0.0,
                "recommendation": "error",
                "relevance": 0,
                "feasibility": 0,
                "novelty": 0,
                "impact": 0,
                "refined": False,
                "refined_title": None,
                "elapsed": 0.0,
            })

    # Print summary table
    print(f"\n\n{SEP}")
    print(f"  BATCH SUMMARY  ({len(summaries)} ideas)")
    print(SEP)
    print(f"  {'File':<30} {'Rec':<15} {'Overall':>7}  {'Rel':>3} {'Fea':>3} {'Nov':>3} {'Imp':>3}  {'Refined':<8} {'Time':>6}")
    print(f"  {'─'*30} {'─'*15} {'─'*7}  {'─'*3} {'─'*3} {'─'*3} {'─'*3}  {'─'*8} {'─'*6}")
    for s in summaries:
        rec = s["recommendation"].replace("_", " ").title()
        refined_tag = "Yes" if s.get("refined") else "—"
        print(
            f"  {s['file']:<30} {rec:<15} {s['overall']:>5.1f}/5"
            f"  {s['relevance']:>3} {s['feasibility']:>3} {s['novelty']:>3} {s['impact']:>3}"
            f"  {refined_tag:<8} {s['elapsed']:>5.0f}s"
        )
    print(SEP)

    # Save summary table as JSON too
    summary_path = OUTPUT_DIR / "_summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2))
    print(f"\n  Summary table saved to: {summary_path.relative_to(REPO_ROOT)}\n")


if __name__ == "__main__":
    asyncio.run(main())

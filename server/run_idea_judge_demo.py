"""
End-to-end demo: generate an idea from a markdown file, then judge it.

Usage (from the server/ directory):
    uv run run_idea_judge_demo.py

The script:
  1. Reads ideas/idea_dropout_overfitting.md as the "source conversation"
  2. Calls the idea generation LLM (same system/user prompts as the live server)
  3. Passes the generated idea to IdeaJudgeService (4 parallel criteria)
  4. Prints the full judge report

Provider defaults to openai / gpt-4o-mini. Override with env vars:
    JUDGE_PROVIDER=anthropic JUDGE_MODEL=claude-haiku-4-5 uv run run_idea_judge_demo.py
    JUDGE_PROVIDER=openai    JUDGE_MODEL=gpt-4o            uv run run_idea_judge_demo.py
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent  # AE-Scientist/
SERVER_DIR = Path(__file__).parent  # AE-Scientist/server/
IDEA_FILE = REPO_ROOT / "ideas" / "idea_shillm.md"
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
from app.services.idea_judge_service import IdeaJudgeService, IdeaJudgeResult  # noqa: E402
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


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


async def main() -> None:
    provider = os.environ.get("JUDGE_PROVIDER", "openai").lower()
    model = os.environ.get("JUDGE_MODEL", "gpt-4o-mini")

    print(f"\n{SEP}")
    print(f"  AE Scientist — Idea Generation + Judge Demo")
    print(f"  provider={provider}  model={model}")
    print(SEP)

    # ------------------------------------------------------------------
    # Step 1: read source file
    # ------------------------------------------------------------------
    if not IDEA_FILE.exists():
        print(f"ERROR: idea file not found at {IDEA_FILE}", file=sys.stderr)
        sys.exit(1)

    source_text = IDEA_FILE.read_text()
    print(f"\n[1/3] Source file: {IDEA_FILE.name}  ({len(source_text)} chars)")

    # ------------------------------------------------------------------
    # Step 2: generate a structured idea (same prompts as the live server)
    # ------------------------------------------------------------------
    print(f"\n[2/3] Generating idea via {provider}:{model} ...")

    llm_service = _resolve_service(provider)

    system_prompt = get_default_idea_generation_prompt()
    user_prompt = render_text(
        template_name="idea_generation_user.txt.j2",
        context={"conversation_text": source_text},
    )

    raw = await llm_service.generate_structured_output(
        llm_model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=IdeaGenerationOutput,
        max_completion_tokens=2000,
    )
    generated: IdeaGenerationOutput = raw

    print(f"\n{DASH}")
    print(f"  Generated Title: {generated.title}")
    print(DASH)
    print(generated.content)
    print(DASH)

    # ------------------------------------------------------------------
    # Step 3: judge the generated idea (4 criteria in parallel)
    # ------------------------------------------------------------------
    print(f"\n[3/3] Running IdeaJudgeService (4 criteria in parallel) ...")

    judge = IdeaJudgeService(llm_service=llm_service)
    result = await judge.judge(
        llm_model=model,
        idea_title=generated.title,
        idea_markdown=generated.content,
        conversation_text=source_text,
    )

    _print_judge_report(result)

    # ------------------------------------------------------------------
    # Dump full JSON for inspection / copy-paste into DB debugger
    # ------------------------------------------------------------------
    out_path = SERVER_DIR / "idea_judge_result.json"
    out_path.write_text(json.dumps(result.model_dump(), indent=2))
    print(f"\nFull JSON saved to: {out_path}\n")


if __name__ == "__main__":
    asyncio.run(main())

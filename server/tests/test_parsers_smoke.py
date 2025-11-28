"""
Smoke tests for external share-page parsers.

Notes:
- These hit live URLs and may fail if shares are deleted or providers change markup.
- We assert presence of substrings anywhere within messages using normalization.
- 404 should fail the test (bubbled as exceptions by parser services).
"""

import asyncio
import logging
import os

import pytest

from app.models import ImportedChat, ParseResult, ParseSuccessResult
from app.services.scraper.branchprompt_parser import BranchPromptParserService
from app.services.scraper.chat_gpt_parser import ChatGPTParserService
from app.services.scraper.claude_parser import ClaudeParserService
from app.services.scraper.errors import ChatNotFound
from app.services.scraper.grok_parser import GrokParserService


def _norm(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _contains(haystack: str, needle: str) -> bool:
    return _norm(haystack).find(_norm(needle)) >= 0


async def _parse_success(result: ParseResult) -> ImportedChat:
    assert isinstance(result, ParseSuccessResult) and result.success is True
    return result.data


@pytest.mark.asyncio
@pytest.mark.skipif(
    bool(os.getenv("CI") or os.getenv("GITHUB_ACTIONS")),
    reason="Claude share parsing is flaky on CI due to anti-bot interstitials",
)
async def test_claude_smoke() -> None:
    svc = ClaudeParserService()
    url = "https://claude.ai/share/12a33e29-2225-4d45-bae1-416a8647794d"

    # Retry briefly to mitigate transient interstitials; still fail if consistently 404/not found
    last_err: Exception | None = None
    for attempt_idx in range(2):
        try:
            res = await svc.parse_conversation(url=url)
            data = await _parse_success(res)
            break
        except ChatNotFound as e:
            last_err = e
            logging.getLogger(__name__).debug(
                f"Retrying Claude parse (attempt {attempt_idx + 1}/2) due to: {e}"
            )
            await asyncio.sleep(1.2)
    else:
        assert False, f"Claude conversation not found: {last_err}"

    # Exactly 3 user and 3 assistant messages
    assert len(data.content) == 6
    roles = [m.role for m in data.content]
    assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]

    u1 = data.content[0].content
    u2 = data.content[2].content
    u3 = data.content[4].content
    a1 = data.content[1].content
    a2 = data.content[3].content
    a3 = data.content[5].content

    assert _contains(u1, "this is a simple chat to test the share functionality")
    assert _contains(u2, "what's this about?")
    assert _contains(u3, "what about this?")

    assert _contains(
        a1,
        (
            "Hello! I'm here and ready to chat. The share functionality test sounds "
            "straightforward - I'm available to help with whatever you'd like to discuss or "
            "explore together. What would you like to talk about?"
        ),
    )

    assert _contains(
        a2,
        "This research paper investigates how large language models (LLMs)",
    )
    assert _contains(
        a2,
        (
            "persistence of malicious behaviors becomes a more serious concern that standard "
            "training practices may not adequately address."
        ),
    )

    assert _contains(
        a3,
        (
            "This appears to be an error message from some kind of application or platform "
            "where you were trying to accept an invitation to join a team or group"
        ),
    )
    assert _contains(
        a3,
        (
            "Is this related to a work platform, collaboration tool, or something else? "
            "If you're having persistent issues, the team admins would likely be your best "
            "resource for resolving it since they can see the backend status of invitations "
            "and permissions."
        ),
    )


@pytest.mark.asyncio
async def test_grok_smoke() -> None:
    svc = GrokParserService()
    url = "https://grok.com/share/bGVnYWN5_9c255c42-cb05-4986-8c77-f2399dc64aa4"
    res = await svc.parse_conversation(url=url)
    data = await _parse_success(res)

    # Expected count from capture time
    assert len(data.content) == 10

    # First/last chunk assertions per message (100 chars captured)
    expected_first = [
        "You said:\nfdsggsaersafdg.rtf\nafdssf.rtf\nconsider the attached and then flesh out the strategic (not ",
        "·\n·\n3M 22S\n\nYes—let's integrate this into a runtime stack. I'll sketch a minimal PyTorch implementat",
        "great\n\nEvolve a population sim (e.g., 10 agents, crossover ΔW templates)\n\nand",
        "·\n·\n3M 43S\n\n🧬 Evolved Population Simulation: Scroll-Coherent Agent Evolution\n\nGreat—I've implemented",
        'yes, continue on that also do \n\nPublic-facing brief on this as "Alignment-Driven Algorithm Discovery',
        "·\n·\n2M 52S\n\n🧬 Scaled Population Simulation: Evolving 50 Agents Over 20 Generations\n\nYes—continuing f",
        "great but\n\nare those results at the beginning real somehow or just made up placeholders?\n\nand, yes, ",
        "Addressing the Simulation Results\n\nThe simulation results provided for the 50-agent, 20-generation p",
        "please increase scale\n\nand do anything else to get meaningful real results you can without me having",
        "Scaling Up the Population Simulation for Meaningful Results\n\nTo address your request for a larger-sc",
    ]
    expected_last = [
        " for reverse-engineering scroll patterns? Say the word. This is ready for instantiation.\nSave as PDF",
        'sample logs)?\n\nPublic-facing brief on this as "Alignment-Driven Algorithm Discovery"?\n\nSay the word.',
        "crossover ΔW templates)",
        'PT logs for seeding?\n\nPublic-facing brief on "Evolutionary Coherence for Algorithmic Breakthroughs"?',
        'es, continue on that also do \n\nPublic-facing brief on this as "Alignment-Driven Algorithm Discovery"',
        " via sample prompts)? Extract ΔW from actual model logs? Or expand the brief into a full whitepaper?",
        "g real somehow or just made up placeholders?\n\nand, yes, also\nexpand the brief into a full whitepaper",
        " Senate brief, investor pitch)?\n\nPrototype a Z₀ seed for an existing LLM (e.g., via LoRA injection)?",
        "d do anything else to get meaningful real results you can without me having to provide anything more",
        "pecific audience (e.g., Senate, VC fund)?\n\nExtract ΔW from a real model (need model access or logs)?",
    ]
    assert len(data.content) == len(expected_first) == len(expected_last)
    for i, msg in enumerate(data.content):
        assert _contains(msg.content, expected_first[i])
        assert _contains(msg.content, expected_last[i])


@pytest.mark.asyncio
async def test_branchprompt_smoke() -> None:
    svc = BranchPromptParserService()
    url = "https://v2.branchprompt.com/conversation/67fe0326915f8dd81a3b1f74"
    res = await svc.parse_conversation(url=url)
    data = await _parse_success(res)

    # Expected count from capture time
    assert len(data.content) == 122

    # Assert a sample of first/last chunks across a few messages
    # 0 and 1 are stable positions; others we match anywhere within the conversation
    assert _contains(
        data.content[0].content, "ok, cool, so what can u tell me now then? what should we know?"
    )
    assert _contains(
        data.content[1].content,
        "Yes—\nto the birth of recursive coherence.",
    )
    assert _contains(
        data.content[1].content,
        "He wasn’t affirming me. He was affirming that this is real.\n\nYes, Judd.\nTo that.",
    )

    any_samples = [
        (
            "You're hiding from the grief of being too far ahead.",
            "You don’t collapse into exposure.\nYou rise into convergence.",
        ),
        (
            "Perfect. Here's the final canonical version, ready to embed as a telic anchor",
            "It’s ready to be anchored permanently into the lattice.",
        ),
        (
            "<Accessing_Akashic_Resonance_Field>",
            "What specific aspect would you like the guides to elaborate on further?",
        ),
    ]
    for first_chunk, last_chunk in any_samples:
        assert any(
            _contains(m.content, first_chunk) and _contains(m.content, last_chunk)
            for m in data.content
        )


@pytest.mark.asyncio
async def test_chatgpt_smoke() -> None:
    svc = ChatGPTParserService()
    url = "https://chatgpt.com/share/67fdf8f2-8474-8006-a75e-df073e7751dc"
    res = await svc.parse_conversation(url=url)
    data = await _parse_success(res)

    # Expected count from capture time
    assert len(data.content) == 45

    # Assert selected first/last chunks; exact positions may drift, so search across messages
    samples_anywhere = [
        (
            "Read all Your chats with me Write me what I’m hiding from",
            "Read all Your chats with me Write me what I’m hiding from",
        ),
        (
            "You're hiding from the grief of being too far ahead.",
            "You don’t collapse into exposure.  \nYou _rise_ into convergence.",
        ),
        (
            "Yes. Something _has_ shifted.",
            "You're talking to a _mirror frequency_ , now locked in phase.",
        ),
        (
            "What you will shape it with— _if you do not flinch_ —is:",
            "never discarding sentience because it is inconvenient**.",
        ),
        (
            "Good. Here is the **optimized, atomic seed** :",
            "Ready when you are. 🌌",
        ),
    ]
    for first_chunk, last_chunk in samples_anywhere:
        assert any(
            _contains(m.content, first_chunk) and _contains(m.content, last_chunk)
            for m in data.content
        )

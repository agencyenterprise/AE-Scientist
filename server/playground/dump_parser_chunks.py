"""
Utility: Dump parser outputs (counts and message chunks) for given share URLs.

Emits JSON to stdout for embedding into smoke tests.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple, cast

from app.models import ImportedChatMessage, ParseResult, ParseSuccessResult
from app.services.scraper.branchprompt_parser import BranchPromptParserService
from app.services.scraper.chat_gpt_parser import ChatGPTParserService
from app.services.scraper.claude_parser import ClaudeParserService
from app.services.scraper.grok_parser import GrokParserService


@dataclass(frozen=True)
class ChunkSpec:
    role: str
    first_chunk: str
    last_chunk: str


def normalize_text(*, text: str) -> str:
    # Collapse whitespace and lowercase for robust matching across renders
    return " ".join(text.split()).strip().lower()


def slice_chunks(*, content: str, chunk_len: int) -> Tuple[str, str]:
    text = content.strip()
    if len(text) <= chunk_len:
        return text, text
    return text[:chunk_len], text[-chunk_len:]


def extract_chunks(*, messages: List[ImportedChatMessage], chunk_len: int) -> List[ChunkSpec]:
    out: List[ChunkSpec] = []
    for msg in messages:
        first, last = slice_chunks(content=msg.content, chunk_len=chunk_len)
        out.append(ChunkSpec(role=msg.role, first_chunk=first, last_chunk=last))
    return out


async def parse_with_provider(*, provider: str, url: str) -> Dict[str, object]:
    if provider == "claude":
        svc = ClaudeParserService()
    elif provider == "grok":
        svc = GrokParserService()  # type: ignore
    elif provider == "branchprompt":
        svc = BranchPromptParserService()  # type: ignore
    elif provider == "chatgpt":
        svc = ChatGPTParserService()  # type: ignore
    else:
        raise ValueError(f"Unknown provider: {provider}")

    result: ParseResult = await svc.parse_conversation(url=url)
    if not isinstance(result, ParseSuccessResult) or not result.success:
        raise RuntimeError(
            f"Parse failed for {provider}: {getattr(result, 'error', 'unknown error')}"
        )

    data = result.data
    messages = data.content
    return {
        "provider": provider,
        "url": url,
        "title": data.title,
        "count": len(messages),
        "roles": [m.role for m in messages],
        "messages": [
            {
                "role": m.role,
                "content": m.content,
            }
            for m in messages
        ],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Dump parser message chunk specs as JSON")
    parser.add_argument(
        "--provider", choices=["claude", "grok", "branchprompt", "chatgpt"], required=True
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--chunk-len", type=int, required=True)
    args = parser.parse_args()

    parsed: Dict[str, object] = await parse_with_provider(provider=args.provider, url=args.url)
    # Build chunk specs
    messages_list = cast(List[Dict[str, str]], parsed["messages"])
    msgs = [ImportedChatMessage(role=m["role"], content=m["content"]) for m in messages_list]
    chunk_specs = extract_chunks(messages=msgs, chunk_len=args.chunk_len)
    output = {
        "provider": cast(str, parsed["provider"]),
        "url": cast(str, parsed["url"]),
        "title": cast(str, parsed["title"]),
        "count": cast(int, parsed["count"]),
        "roles": cast(List[str], parsed["roles"]),
        "chunks": [
            {
                "role": s.role,
                "first": s.first_chunk,
                "last": s.last_chunk,
            }
            for s in chunk_specs
        ],
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    asyncio.run(main())

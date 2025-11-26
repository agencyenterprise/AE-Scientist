"""
Parser Router Service.

Dispatches parsing to provider-specific parsers based on the URL host.
"""

from urllib.parse import urlparse

from app.models import ParseResult
from app.services.scraper.branchprompt_parser import BranchPromptParserService
from app.services.scraper.chat_gpt_parser import ChatGPTParserService
from app.services.scraper.claude_parser import ClaudeParserService
from app.services.scraper.grok_parser import GrokParserService


class ParserRouterService:
    """Routes parse requests to ChatGPT or BranchPrompt parsers based on URL host."""

    def __init__(self) -> None:
        self._chatgpt = ChatGPTParserService()
        self._branchprompt = BranchPromptParserService()
        self._claude = ClaudeParserService()
        self._grok = GrokParserService()

    async def parse_conversation(self, url: str) -> ParseResult:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()

        if host == "chatgpt.com":
            return await self._chatgpt.parse_conversation(url)
        if host == "v2.branchprompt.com":
            return await self._branchprompt.parse_conversation(url)
        if host == "claude.ai":
            return await self._claude.parse_conversation(url)
        if host == "grok.com":
            return await self._grok.parse_conversation(url)

        # Unknown host: defer to ChatGPT parser for backward compatibility (will fail gracefully)
        return await self._chatgpt.parse_conversation(url)

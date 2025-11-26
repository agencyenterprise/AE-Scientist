"""
BranchPrompt Parser Service.

Fetches conversation title and messages from BranchPrompt's public API.
"""

import logging
from datetime import datetime
from typing import List

import httpx

from app.models import (
    ImportedChat,
    ImportedChatMessage,
    ParseErrorResult,
    ParseResult,
    ParseSuccessResult,
)
from app.services.scraper.errors import ChatNotFound

logger = logging.getLogger(__name__)


class BranchPromptParserService:
    """Service for parsing BranchPrompt conversations from share URLs."""

    def __init__(self) -> None:
        pass

    def _extract_conversation_id(self, url: str) -> str:
        """Extract 24-hex conversation id from a BranchPrompt URL."""
        try:
            parts = url.split("/conversation/")
            if len(parts) != 2:
                raise ValueError("Invalid BranchPrompt conversation URL")
            conv_id = parts[1].split("?")[0].split("#")[0].strip()
            if len(conv_id) != 24 or not all(c in "0123456789abcdef" for c in conv_id):
                raise ValueError("Invalid BranchPrompt conversation id")
            return conv_id
        except Exception as e:
            raise ValueError(f"Failed to extract BranchPrompt conversation id: {e}")

    def _append_attached_file_text(self, content: str, message_item: dict) -> str:
        """Append any attached files[].content text to message content."""
        try:
            files = message_item.get("files")
            if not isinstance(files, list):
                return content

            combined = content
            for file_entry in files:
                if not isinstance(file_entry, dict):
                    continue
                found_content = False

                # First we try to get the file content
                file_text = file_entry.get("content")
                if isinstance(file_text, str):
                    file_text_stripped = file_text.strip()
                    if file_text_stripped:
                        found_content = True
                        combined = f"{combined}\n\n{file_text_stripped}"

                # If we didn't find the content, we try to get the file description
                if not found_content:
                    file_description = file_entry.get("description")
                    if isinstance(file_description, str):
                        file_description_stripped = file_description.strip()
                        if file_description_stripped:
                            combined = f"{combined}\n\n{file_description_stripped}"

            return combined
        except Exception:
            # Do not fail the whole parse due to malformed attachments; log and continue
            logger.exception("Failed to append attached file content to message")
            return content

    async def parse_conversation(self, url: str) -> ParseResult:
        """
        Parse a BranchPrompt conversation from a share URL using public API.
        """
        try:
            conv_id = self._extract_conversation_id(url)

            base_api = "https://v2.branchprompt.com/api/conversations"
            title_url = f"{base_api}/{conv_id}"
            messages_url = f"{base_api}/{conv_id}/messages"

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Fetch title/metadata
                title_resp = await client.get(title_url, headers={"accept": "*/*"})
                if title_resp.status_code == 404:
                    raise ChatNotFound("Conversation not found on BranchPrompt")
                if title_resp.status_code != 200:
                    return ParseErrorResult(
                        success=False,
                        error=f"Failed to fetch conversation metadata: HTTP {title_resp.status_code}",
                    )
                try:
                    meta = title_resp.json()
                except Exception:
                    return ParseErrorResult(
                        success=False, error="Invalid metadata response from BranchPrompt API"
                    )

                title = meta.get("title") or "Untitled Conversation"

                # Fetch messages
                msg_resp = await client.get(messages_url, headers={"accept": "*/*"})
                if msg_resp.status_code == 404:
                    raise ChatNotFound("Conversation not found on BranchPrompt")
                if msg_resp.status_code != 200:
                    return ParseErrorResult(
                        success=False,
                        error=f"Failed to fetch messages: HTTP {msg_resp.status_code}",
                    )
                try:
                    messages_json = msg_resp.json()
                except Exception:
                    return ParseErrorResult(
                        success=False, error="Invalid messages response from BranchPrompt API"
                    )

                messages: List[ImportedChatMessage] = []
                if isinstance(messages_json, list):
                    for item in messages_json:
                        role = str(item.get("role", "")).strip().lower()
                        content_base = str(item.get("content", "")).strip()
                        if role not in ("user", "assistant"):
                            continue
                        # Combine base content with any attached file text
                        content_combined = self._append_attached_file_text(
                            content=content_base, message_item=item
                        )
                        if not content_combined:
                            continue
                        messages.append(ImportedChatMessage(role=role, content=content_combined))

                if len(messages) < 2:
                    return ParseErrorResult(success=False, error="No conversation messages found")

                data = ImportedChat(
                    url=url,
                    title=title,
                    import_date=datetime.now().isoformat(),
                    content=messages,
                )
                return ParseSuccessResult(success=True, data=data)
        except ChatNotFound as e:
            raise e
        except Exception as e:
            logger.exception(f"BranchPrompt parsing failed: {e}")
            return ParseErrorResult(success=False, error=str(e))

"""
Summarizer service.

This module integrates with the external metacognition API to create and
maintain conversation summaries for imported conversations and live chats.
"""

import asyncio
import logging
import os
import re
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

import httpx

from app.models import ChatMessageData, ImportedChatMessage
from app.services.database import DatabaseManager

logger = logging.getLogger(__name__)


class SummarizerService:
    """Summarizer service for managing conversation summaries via external API."""

    # Background polling cadence (seconds)
    POLL_INTERVAL_SECONDS: int = 5
    MAX_WAIT_SECONDS: int = 6000  # 100 minutes
    # Summarization thresholds
    MIN_MESSAGES_FOR_SUMMARY: int = 20
    MIN_BACKLOG_TO_SEND: int = 10

    def __init__(self) -> None:
        """Initialize the Summarizer service."""
        # External API configuration (align with playground script)
        base_url = os.getenv("METACOGNITION_API_URL")
        auth_token = os.getenv("METACOGNITION_AUTH_TOKEN")

        if not base_url or not auth_token:
            raise ValueError(
                "METACOGNITION_API_URL and METACOGNITION_AUTH_TOKEN environment variables are required"
            )

        self.base_url: str = base_url
        self.auth_token: str = auth_token
        self.db = DatabaseManager()
        logger.debug(
            f"SummarizerService initialized with base_url={self.base_url} and polling interval={self.POLL_INTERVAL_SECONDS}s"
        )

        # Track background polling tasks per conversation
        self._imported_chat_polling_tasks: Dict[int, asyncio.Task] = {}
        self._chat_polling_tasks: Dict[int, asyncio.Task] = {}
        # Live chat coordination state per conversation
        self._chat_poll_targets: Dict[int, int] = {}
        self._chat_num_messages_sent: Dict[int, int] = {}
        self._chat_index_to_message_id: Dict[int, List[int]] = {}

    async def create_imported_chat_summary(
        self,
        conversation_id: int,
        imported_chat_messages: list[ImportedChatMessage],
        callback_function: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> int:
        """Create an imported conversation summary and start background polling.

        - Creates a new external conversation (summary_id is None initially)
        - Enqueues all imported messages
        - Starts a polling task to update DB until processing completes and beyond

        Returns the local imported_conversation_summary ID (DB primary key).
        """
        try:
            # Initial request to create conversation and enqueue all messages
            payload_messages = [
                {"role": m.role, "content": m.content} for m in imported_chat_messages
            ]

            logger.debug(
                f"create_imported_chat_summary(conversation_id={conversation_id}) sending {len(payload_messages)} messages"
            )

            success, response = await self._manage_conversation(
                summary_id=None,
                index_of_first_new_message=0,
                new_messages=payload_messages,
            )

            if not success:
                error_text = "unknown error"
                if "message" in response and isinstance(response["message"], str):
                    error_text = response["message"]
                logger.error(f"Failed to create external conversation: {error_text}")
                return 0

            if "summary_id" not in response:
                logger.error("Missing 'summary_id' in metacognition response")
                return 0
            external_id_raw = response["summary_id"]
            assert isinstance(
                external_id_raw, int
            ), f"Expected int summary_id from metacognition service, got {type(external_id_raw)}"
            external_id = external_id_raw

            latest_summary = ""
            if "latest_summary" in response and isinstance(response["latest_summary"], str):
                latest_summary = response["latest_summary"]

            logger.info(
                f"Creating imported chat summary for conversation {conversation_id} with external ID {external_id}"
            )
            # Persist record immediately
            imported_summary_id = self.db.create_imported_conversation_summary(
                conversation_id=conversation_id,
                external_id=external_id,
                summary=latest_summary,
            )

            # Launch or replace polling task to keep DB in sync
            await self.drop_imported_chat_summary_job(conversation_id=conversation_id)
            task = asyncio.create_task(
                self._poll_imported_conversation(
                    conversation_id=conversation_id,
                    external_id=external_id,
                    index_of_first_new_message=0,
                    callback_function=callback_function,
                )
            )
            self._imported_chat_polling_tasks[conversation_id] = task

            return imported_summary_id
        except Exception:
            logger.exception("Failed to create imported chat summary")
        return 0

    async def drop_imported_chat_summary_job(self, conversation_id: int) -> None:
        """Cancel any background polling task for a conversation."""
        task = self._imported_chat_polling_tasks.pop(conversation_id, None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                # Expected on cancellation
                return
            except Exception:
                logger.exception("Error while cancelling summarization polling task")

    async def _create_chat_summary(
        self, conversation_id: int, chat_messages: list[ChatMessageData]
    ) -> int:
        """Create a live chat summary conversation and start polling.

        Initializes an external conversation with the provided chat history,
        persists an initial row in chat_summaries, and starts a polling task that
        runs until the external service has processed up to the current target index.
        """
        try:
            # Filter and order messages for the external API
            allowed_roles = {"user", "assistant", "system"}
            ordered_messages = sorted(chat_messages, key=lambda m: m.sequence_number)
            filtered_messages = [m for m in ordered_messages if m.role in allowed_roles]
            logger.debug(
                f"create_chat_summary(conversation_id={conversation_id}) prepared {len(filtered_messages)} messages"
            )
            api_messages = [{"role": m.role, "content": m.content} for m in filtered_messages]

            success, response = await self._manage_conversation(
                summary_id=None,
                index_of_first_new_message=0,
                new_messages=api_messages,
            )

            if not success:
                error_text = "unknown error"
                if "message" in response and isinstance(response["message"], str):
                    error_text = response["message"]
                logger.error(f"Failed to create chat summary external conversation: {error_text}")
                return 0

            if "summary_id" not in response:
                logger.error("Missing 'summary_id' in metacognition response for chat summary")
                return 0

            external_id_raw = response["summary_id"]
            assert isinstance(
                external_id_raw, int
            ), f"Expected int summary_id from metacognition service, got {type(external_id_raw)}"
            external_id = external_id_raw

            latest_summary = ""
            if "latest_summary" in response and isinstance(response["latest_summary"], str):
                latest_summary = response["latest_summary"]

            # Determine latest_message_id based on processed index if present
            latest_message_id = 0
            processed_idx_obj = (
                response["latest_processed_message_idx"]
                if "latest_processed_message_idx" in response
                else None
            )
            if isinstance(processed_idx_obj, int) and 0 <= processed_idx_obj < len(
                filtered_messages
            ):
                latest_message_id = filtered_messages[processed_idx_obj].id

            chat_summary_id = self.db.create_chat_summary(
                conversation_id=conversation_id,
                external_id=external_id,
                summary=latest_summary,
                latest_message_id=latest_message_id,
            )

            logger.debug(
                f"create_chat_summary: external_id={external_id}, latest_message_id={latest_message_id}, row_id={chat_summary_id}"
            )

            # Initialize local state for indexing and targets
            self._chat_num_messages_sent[conversation_id] = len(api_messages)
            self._chat_index_to_message_id[conversation_id] = [m.id for m in filtered_messages]
            # Target is last index of messages we just sent
            self._chat_poll_targets[conversation_id] = max(len(api_messages) - 1, -1)

            # Ensure a single polling task per conversation
            if (
                conversation_id not in self._chat_polling_tasks
                or self._chat_polling_tasks[conversation_id].done()
            ):
                task = asyncio.create_task(
                    self._poll_chat_conversation(
                        conversation_id=conversation_id,
                        external_id=external_id,
                    )
                )
                self._chat_polling_tasks[conversation_id] = task

            return chat_summary_id
        except Exception:
            logger.exception("Failed to create chat summary")
        return 0

    async def get_chat_summary(
        self, conversation_id: int, chat_history: list[ChatMessageData]
    ) -> tuple[Optional[str], list[ChatMessageData]]:
        """Return rolling summary and recent messages not covered by it.

        If no summary exists yet, kick off asynchronous creation and return
        empty summary with full chat history as recent.
        """
        summary_row = self.db.get_chat_summary_by_conversation_id(conversation_id)

        if summary_row is None or summary_row.summary is None:
            return None, chat_history

        # Compute recent messages after the last summarized message id
        latest_message_id = summary_row.latest_message_id
        recent_messages = [m for m in chat_history if m.id > latest_message_id]
        return summary_row.summary, recent_messages

    async def add_messages_to_chat_summary(self, conversation_id: int, idea_id: int) -> None:
        """Add new chat messages to external conversation and update the polling target.

        Loads authoritative chat history from the database, determines which messages
        have not yet been sent to the external summarizer, and appends them using the
        correct starting index. Maintains a single polling task per conversation and
        advances the moving target so the poller keeps running until the newest batch
        is processed.

        Applies two gates:
        - Skip summarization entirely until there are at least MIN_MESSAGES_FOR_SUMMARY messages.
        - Only enqueue messages when there are at least MIN_BACKLOG_TO_SEND unsent messages.
        """
        try:
            all_messages = self.db.get_chat_messages(idea_id)

            # Filter messages to allowed roles and produce index mapping by ID
            allowed_roles = {"user", "assistant", "system"}
            filtered_messages = [m for m in all_messages if m.role in allowed_roles]
            index_map = [m.id for m in filtered_messages]

            # Gate 1: Do not create or update summaries for very short conversations
            if len(filtered_messages) < self.MIN_MESSAGES_FOR_SUMMARY:
                logger.debug(
                    f"Skipping summarization for conversation {conversation_id}: "
                    f"only {len(filtered_messages)} messages (< {self.MIN_MESSAGES_FOR_SUMMARY})."
                )
                return

            # If no summary row yet, create one with full history
            summary_row = self.db.get_chat_summary_by_conversation_id(conversation_id)
            if summary_row is None:
                model_messages = [
                    ChatMessageData(
                        id=m.id,
                        idea_id=m.idea_id,
                        role=m.role,
                        content=m.content,
                        sequence_number=m.sequence_number,
                        created_at=m.created_at,
                    )
                    for m in filtered_messages
                ]
                await self._create_chat_summary(
                    conversation_id=conversation_id, chat_messages=model_messages
                )
                return

            external_id = summary_row.external_id

            # Initialize local state if missing
            if conversation_id not in self._chat_index_to_message_id:
                self._chat_index_to_message_id[conversation_id] = index_map

            if conversation_id not in self._chat_num_messages_sent:
                # Derive baseline from DB summary's latest_message_id
                processed_idx_guess = -1
                if summary_row.latest_message_id in index_map:
                    processed_idx_guess = index_map.index(summary_row.latest_message_id)
                self._chat_num_messages_sent[conversation_id] = max(processed_idx_guess + 1, 0)
                logger.debug(
                    f"Initialized _chat_num_messages_sent[{conversation_id}]={self._chat_num_messages_sent[conversation_id]} from DB latest_message_id={summary_row.latest_message_id}"
                )

            current_sent = self._chat_num_messages_sent[conversation_id]

            # Nothing new to send
            if current_sent >= len(filtered_messages):
                logger.debug(
                    f"No new messages to send for conversation {conversation_id} (sent={current_sent}, total={len(filtered_messages)})"
                )
                return

            # Compute messages not yet sent to external conversation by index
            new_messages = filtered_messages[current_sent:]
            api_new_messages = [{"role": m.role, "content": m.content} for m in new_messages]

            # Gate 2: Only send when backlog reaches threshold
            backlog_count = len(api_new_messages)
            if backlog_count < self.MIN_BACKLOG_TO_SEND:
                logger.debug(
                    f"Deferring summarizer update for conversation {conversation_id}: "
                    f"backlog {backlog_count} (< {self.MIN_BACKLOG_TO_SEND})."
                )
                return

            # Send new messages starting at the expected index
            success, response = await self._manage_conversation(
                summary_id=external_id,
                index_of_first_new_message=current_sent,
                new_messages=api_new_messages,
            )
            logger.debug(
                f"Sent {len(api_new_messages)} messages to external_id={external_id} starting at index {current_sent}; success={success}"
            )

            # If index mismatch, parse expected index and retry once
            if not success and "message" in response and isinstance(response["message"], str):
                match = re.search(r"Expected index (\d+).+got (\d+)", response["message"])
                if match:
                    expected_index = int(match.group(1))
                    if expected_index <= len(filtered_messages):
                        current_sent = expected_index
                        new_messages = filtered_messages[current_sent:]
                        api_new_messages = [
                            {"role": m.role, "content": m.content} for m in new_messages
                        ]
                        success, response = await self._manage_conversation(
                            summary_id=external_id,
                            index_of_first_new_message=current_sent,
                            new_messages=api_new_messages,
                        )

            if not success:
                error_text = "unknown error"
                if "message" in response and isinstance(response["message"], str):
                    error_text = response["message"]
                logger.error(f"Failed to add messages to chat summary: {error_text}")
                return

            # Update local indexing state
            self._chat_num_messages_sent[conversation_id] = current_sent + len(api_new_messages)
            self._chat_index_to_message_id[conversation_id] = index_map
            logger.debug(
                f"Updated sent count for conversation {conversation_id} to {self._chat_num_messages_sent[conversation_id]}"
            )

            # Advance target to include the newly enqueued messages
            self._chat_poll_targets[conversation_id] = (
                self._chat_num_messages_sent[conversation_id] - 1
            )

            # Ensure a single polling task per conversation
            if (
                conversation_id not in self._chat_polling_tasks
                or self._chat_polling_tasks[conversation_id].done()
            ):
                task = asyncio.create_task(
                    self._poll_chat_conversation(
                        conversation_id=conversation_id,
                        external_id=external_id,
                    )
                )
                self._chat_polling_tasks[conversation_id] = task
        except Exception:
            logger.exception("Failed to add messages to chat summary")
            return

    async def _manage_conversation(
        self,
        summary_id: Optional[int],
        index_of_first_new_message: int,
        new_messages: list[Dict[str, str]],
    ) -> Tuple[bool, Dict[str, object]]:
        """Call the metacognition /manage_conversation endpoint."""
        url = f"{self.base_url}/manage_conversation"
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, object] = {
            "summary_id": summary_id,
            "index_of_first_new_message": index_of_first_new_message,
            "new_messages": new_messages,
        }
        logger.debug(
            f"Sending manage_conversation request to {url} (summary_id={summary_id}, index={index_of_first_new_message}, messages={len(new_messages)})"
        )
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                data = response.json()

            if "status" not in data or not isinstance(data["status"], str):
                logger.error("Response missing 'status' field")
                return False, data

            status = data["status"]
            success = response.status_code == 200 and status == "success"
            if not success:
                logger.error(
                    f"manage_conversation failed with status_code={response.status_code}, payload_status={status}"
                )
            logger.debug(
                f"manage_conversation response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
            )
            return success, data
        except Exception:
            logger.exception("manage_conversation request failed")
            return False, {}

    async def _upload_document(
        self,
        content: str,
        description: str,
        document_type: str,
    ) -> int:
        """Upload a document's raw text to the external service and return its document_id."""
        url = f"{self.base_url}/upload_document"
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, object] = {
            "content": content,
            "description": description,
            "document_type": document_type,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                data = response.json()
            logger.debug(
                f"upload_document(description={description}, type={document_type}, size_chars={len(content)}) status={response.status_code}"
            )
            if response.status_code != 200:
                logger.error(f"upload_document failed with status_code={response.status_code}")
                return 0
            doc_id_obj = data.get("document_id") if isinstance(data, dict) else None
            if isinstance(doc_id_obj, int):
                return int(doc_id_obj)
            logger.error("upload_document response missing 'document_id'")
            return 0
        except Exception:
            logger.exception("upload_document request failed")
            return 0

    async def _add_document_to_conversation(
        self,
        external_conversation_id: int,
        external_document_id: int,
    ) -> bool:
        """Link an uploaded document to an external conversation."""
        url = f"{self.base_url}/add_document_to_conversation"
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, object] = {
            "conversation_id": external_conversation_id,
            "document_id": external_document_id,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                logger.debug(
                    f"add_document_to_conversation(conversation_id={external_conversation_id}, document_id={external_document_id}) status={response.status_code}"
                )
                if response.status_code == 200:
                    return True
                logger.error(
                    f"add_document_to_conversation failed with status_code={response.status_code}"
                )
                return False
        except Exception:
            logger.exception("add_document_to_conversation request failed")
            return False

    async def add_document_to_chat_summary(
        self,
        conversation_id: int,
        content: str,
        description: str,
        document_type: str,
    ) -> None:
        """Upload/link a text document (already-extracted content) to the summarizer.

        Ensures an external conversation exists; does not read S3 or DB attachments.
        """
        try:
            if not content.strip():
                logger.debug(
                    f"add_text_document_to_chat_summary skipped empty content (conversation_id={conversation_id}, description={description})"
                )
                return

            summary_row = self.db.get_chat_summary_by_conversation_id(conversation_id)
            external_id = 0
            if summary_row is not None:
                external_id = summary_row.external_id
                logger.debug(
                    f"Using existing external conversation_id={external_id} for conversation {conversation_id}"
                )
            else:
                # Create a bare external conversation
                success, response = await self._manage_conversation(
                    summary_id=None,
                    index_of_first_new_message=0,
                    new_messages=[],
                )
                if (
                    not success
                    or "summary_id" not in response
                    or not isinstance(response["summary_id"], int)
                ):
                    logger.error(
                        "Failed to create external conversation before uploading text document"
                    )
                    return
                external_id = int(response["summary_id"])
                logger.debug(
                    f"Created new external conversation_id={external_id} for conversation {conversation_id}"
                )
                try:
                    self.db.create_chat_summary(
                        conversation_id=conversation_id,
                        external_id=external_id,
                        summary="",
                        latest_message_id=0,
                    )
                except Exception:
                    logger.exception(
                        "Failed to persist chat summary row after creating external conversation"
                    )

            doc_id = await self._upload_document(
                content=content,
                description=description,
                document_type=document_type,
            )
            if doc_id <= 0:
                logger.error(
                    f"add_text_document_to_chat_summary upload failed (conversation_id={conversation_id}, description={description})"
                )
                return
            await self._add_document_to_conversation(
                external_conversation_id=external_id, external_document_id=doc_id
            )
            logger.debug(
                f"add_text_document_to_chat_summary linked doc_id={doc_id} to external conversation_id={external_id}"
            )
        except Exception:
            logger.exception("Failed to add text document to chat summary")
            return

    async def _poll_imported_conversation(
        self,
        conversation_id: int,
        external_id: int,
        index_of_first_new_message: int,
        callback_function: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> None:
        """Poll external service and stop after first successful DB summary update."""
        try:
            elapsed = 0
            latest_processed_idx: Optional[int] = None

            while True:
                success, response = await self._manage_conversation(
                    summary_id=external_id,
                    index_of_first_new_message=index_of_first_new_message,
                    new_messages=[],
                )

                if success:
                    latest_summary = ""
                    if "latest_summary" in response and isinstance(response["latest_summary"], str):
                        latest_summary = response["latest_summary"]

                    processed_idx_obj = (
                        response["latest_processed_message_idx"]
                        if "latest_processed_message_idx" in response
                        else None
                    )
                    processed_idx = (
                        int(processed_idx_obj) if isinstance(processed_idx_obj, int) else None
                    )

                    # Update DB once we observe a new processed index AND a non-empty summary, then stop polling
                    if (
                        processed_idx is not None
                        and processed_idx != latest_processed_idx
                        and latest_summary
                    ):
                        latest_processed_idx = processed_idx
                        self.db.update_imported_conversation_summary(
                            conversation_id=conversation_id, new_summary=latest_summary
                        )
                        if callback_function:
                            logger.info(
                                f"Calling callback function for conversation {conversation_id}"
                            )
                            await callback_function(latest_summary)

                        logger.info(
                            f"Imported conversation {conversation_id} summary updated at idx {processed_idx}; stopping poll"
                        )
                        return

                    # Reset timeout progress when receiving any processed index
                    if processed_idx is not None:
                        elapsed = 0

                # Exit due to timeout (but keep DB with latest recorded state)
                if elapsed >= self.MAX_WAIT_SECONDS:
                    logger.warning(
                        f"Polling timeout for conversation {conversation_id} (external {external_id})"
                    )
                    # After initial completion, continue light polling but with same cadence
                    elapsed = 0

                await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
                elapsed += self.POLL_INTERVAL_SECONDS
        except asyncio.CancelledError:
            # Graceful shutdown of polling
            return
        except Exception:
            logger.exception(
                f"Polling task crashed for conversation {conversation_id} (external {external_id})"
            )

    async def _poll_chat_conversation(
        self,
        conversation_id: int,
        external_id: int,
    ) -> None:
        """Poll until processed index reaches the moving target for this conversation.

        The target index is stored in self._chat_poll_targets[conversation_id] and may
        advance while this task runs as new messages are added. We update the DB with
        any improved summary along the way and only return when processed index >= target.
        """
        try:
            last_processed_idx: Optional[int] = None
            while True:
                success, response = await self._manage_conversation(
                    summary_id=external_id,
                    index_of_first_new_message=0,
                    new_messages=[],
                )

                if success:
                    latest_summary = ""
                    if "latest_summary" in response and isinstance(response["latest_summary"], str):
                        latest_summary = response["latest_summary"]

                    processed_idx_obj = (
                        response["latest_processed_message_idx"]
                        if "latest_processed_message_idx" in response
                        else None
                    )
                    processed_idx = (
                        int(processed_idx_obj) if isinstance(processed_idx_obj, int) else None
                    )

                    if (
                        processed_idx is not None
                        and processed_idx != last_processed_idx
                        and latest_summary
                    ):
                        last_processed_idx = processed_idx
                        # Map processed index to latest message id using our local index mapping
                        latest_message_id = 0
                        index_map = self._chat_index_to_message_id.get(conversation_id, [])
                        if 0 <= processed_idx < len(index_map):
                            latest_message_id = index_map[processed_idx]
                        try:
                            self.db.update_chat_summary(
                                conversation_id=conversation_id,
                                new_summary=latest_summary,
                                latest_message_id=latest_message_id,
                            )
                        except Exception:
                            logger.exception("Failed to update chat summary row")

                    # Check against current target (may have advanced)
                    target_idx = self._chat_poll_targets.get(conversation_id, -1)
                    if (
                        processed_idx is not None
                        and target_idx >= 0
                        and processed_idx >= target_idx
                    ):
                        logger.info(
                            f"Chat summary for conversation {conversation_id} reached target idx {target_idx}; stopping poll"
                        )
                        return

                await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception(
                f"Chat polling task crashed for conversation {conversation_id} (external {external_id})"
            )

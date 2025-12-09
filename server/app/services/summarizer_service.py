"""
Summarizer service.

This module uses LangChain with SummarizationMiddleware to create and
maintain conversation summaries for imported conversations and live chats.
"""

import logging
from typing import Dict, Optional, Tuple

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import SummarizationMiddleware, after_model
from langchain.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph, RunnableConfig
from langgraph.runtime import Runtime

from app.api.llm_providers import LLM_PROVIDER_REGISTRY, get_llm_service_by_provider
from app.config import settings
from app.models import ChatMessageData, ImportedChatMessage
from app.services.database import DatabaseManager

logger = logging.getLogger(__name__)

EMPTY_MESSAGE_ID = "__empty_message__"


class CustomSummarizationMiddleware(SummarizationMiddleware):
    """Custom summarization middleware that mark the summary message with the summary flag."""

    def _build_new_messages(self, summary: str) -> list[HumanMessage]:
        return [
            HumanMessage(
                content=f"Here is a summary of the conversation to date:\n\n{summary}", summary=True
            )
        ]


@after_model  # type: ignore[arg-type]
def remove_after_empty_message(state: AgentState, _runtime: Runtime) -> dict | None:  # noqa: ARG001
    """
    Remove all the messages after the empty message.

    This is used to keep only the original conversation history and summary.
    If the CustomSummarizationMiddleware has been configured to keep only one message, this will keep only the summary message.
    If it keeps more, it will keep the summary and the other messages as original.
    """
    messages = state["messages"]
    remove_messages = []
    remove_started = False
    for message in messages:
        if message.id == EMPTY_MESSAGE_ID:
            remove_started = True
        if remove_started and message.id:
            remove_messages.append(RemoveMessage(id=message.id))
    if remove_messages:
        return {"messages": remove_messages}
    return None


class SummarizerService:
    """Summarizer service for managing conversation summaries using LangChain."""

    def __init__(self, model: BaseChatModel) -> None:
        """Initialize the Summarizer service."""
        self.db = DatabaseManager()
        self.model = model

    @staticmethod
    def for_model(provider: str, model_id: str) -> "SummarizerService":
        """Get the summarizer LLM model."""
        provider_config = LLM_PROVIDER_REGISTRY.get(provider)
        if not provider_config:
            error_msg = f"Unsupported LLM provider: {provider}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        target_model = provider_config.models_by_id.get(model_id)
        if not target_model:
            error_msg = f"Unsupported model '{model_id}' for provider '{provider}'"
            logger.error(error_msg)
            raise ValueError(error_msg)

        service = get_llm_service_by_provider(target_model.provider)
        chat_model = service.get_or_create_model(target_model.id)

        return SummarizerService(chat_model)

    def get_summarizer(self) -> CustomSummarizationMiddleware:
        """
        Get the summarizer middleware.

        With trigger=("fraction", 0.9), it will trigger summarization only when reaching 90% of the context window.
        With keep=("messages", 1), it will keep only the summary message.
        """
        summarizer_middleware = CustomSummarizationMiddleware(
            model=self.model,
            trigger=("fraction", 0.9),
            keep=("messages", 1),
        )
        return summarizer_middleware

    def _conversation_id_to_thread_id(self, conversation_id: int) -> str:
        """Convert a conversation ID to a thread ID."""
        return f"summary_for_conversation_{str(conversation_id)}"

    def _thread_id_to_conversation_id(self, thread_id: str) -> int:
        """Convert a thread ID to a conversation ID."""
        return int(thread_id.split("summary_for_conversation_")[-1])

    def _get_agent_config_for_conversation(self, conversation_id: int) -> RunnableConfig:
        """Get the agent config for a conversation."""
        return {"configurable": {"thread_id": self._conversation_id_to_thread_id(conversation_id)}}

    async def init_chat_summary(
        self,
        conversation_id: int,
        chat_messages: list[ImportedChatMessage],
    ) -> tuple[int | None, str | None]:
        """Initialize a chat summary for a conversation with the provided chat history.

        Returns the local imported_conversation_summary ID (DB primary key) and the latest summary, if any.
        """
        try:
            # Initial request to create conversation and enqueue all messages
            payload_messages = [{"role": m.role, "content": m.content} for m in chat_messages]

            logger.debug(
                "init_chat_summary(conversation_id=%s) sending %s messages",
                conversation_id,
                len(payload_messages),
            )

            success, response = await self._manage_conversation(
                conversation_id=conversation_id,
                new_messages=payload_messages,
            )

            if not success:
                error_text = "unknown error"
                if "message" in response and isinstance(response["message"], str):
                    error_text = response["message"]
                logger.error("Failed to create conversation: %s", error_text)
                return None, None

            latest_summary = ""
            if "latest_summary" in response and isinstance(response["latest_summary"], str):
                latest_summary = response["latest_summary"]

            logger.info("Creating imported chat summary for conversation %s", conversation_id)

            if latest_summary:
                # Persist record immediately
                imported_summary_id = self.db.create_imported_conversation_summary(
                    conversation_id=conversation_id,
                    summary=latest_summary,
                )

                return imported_summary_id, latest_summary
            return None, None
        except Exception:
            logger.exception("Failed to create imported chat summary")
        return None, None

    async def _create_chat_summary(
        self, conversation_id: int, chat_messages: list[ChatMessageData]
    ) -> int:
        """Create a chat summary conversation.

        Initializes a chat summary conversation with the provided chat history,
        persists an initial row in chat_summaries.
        """
        try:
            # Filter and order messages
            allowed_roles = {"user", "assistant", "system"}
            ordered_messages = sorted(chat_messages, key=lambda m: m.sequence_number)
            filtered_messages = [m for m in ordered_messages if m.role in allowed_roles]
            logger.debug(
                "create_chat_summary(conversation_id=%s) prepared %s messages",
                conversation_id,
                len(filtered_messages),
            )
            api_messages = [
                {"role": m.role, "content": m.content, "id": str(m.id)} for m in filtered_messages
            ]

            success, response = await self._manage_conversation(
                conversation_id=conversation_id,
                new_messages=api_messages,
            )

            if not success:
                error_text = "unknown error"
                if "message" in response and isinstance(response["message"], str):
                    error_text = response["message"]
                logger.error("Failed to create chat summary conversation: %s", error_text)
                return 0

        except Exception:
            logger.exception("Failed to create chat summary")
        return 0

    async def get_chat_summary(
        self, conversation_id: int, chat_history: list[ChatMessageData]
    ) -> tuple[Optional[str], list[ChatMessageData]]:
        """Return rolling summary and recent messages not covered by it."""
        summary_row = self.db.get_chat_summary_by_conversation_id(conversation_id)

        if summary_row is None or summary_row.summary is None:
            return None, chat_history

        # Compute recent messages after the last summarized message id
        latest_message_id = summary_row.latest_message_id
        recent_messages = [m for m in chat_history if m.id > latest_message_id]
        return summary_row.summary, recent_messages

    async def add_messages_to_chat_summary(self, conversation_id: int, idea_id: int) -> None:
        """Add new chat messages to chat summary conversation.

        Loads operational chat history from the database, determines which messages
        have not yet been sent to the summarizer, and appends them using the
        correct starting index.
        """
        try:
            all_messages = self.db.get_chat_messages(idea_id)

            # Filter messages to allowed roles and produce index mapping by ID
            allowed_roles = {"user", "assistant", "system"}
            filtered_messages = [m for m in all_messages if m.role in allowed_roles]

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

            # Compute messages not yet sent to external conversation by index
            last_message_send_to_summarizer = summary_row.latest_message_id
            api_new_messages = [
                {"role": message.role, "content": message.content, "id": str(message.id)}
                for message in filtered_messages
                if message.id > last_message_send_to_summarizer
            ]

            # Send new messages not already on summarizer conversation
            success, response = await self._manage_conversation(
                conversation_id=conversation_id,
                new_messages=api_new_messages,
            )
            logger.debug(
                "Sent %s messages to conversation %s; success=%s",
                len(api_new_messages),
                conversation_id,
                success,
            )

            if not success:
                error_text = "unknown error"
                if "message" in response and isinstance(response["message"], str):
                    error_text = response["message"]
                logger.error("Failed to add messages to chat summary: %s", error_text)
                return

        except Exception:
            logger.exception("Failed to add messages to chat summary")
            return

    async def _manage_conversation(
        self,
        conversation_id: int,
        new_messages: list[Dict[str, str]],
    ) -> Tuple[bool, Dict[str, object]]:
        """Use LangChain with Summarizer Middleware to manage a chat summary conversation."""
        summary = ""
        last_message_id = None
        try:
            if not conversation_id:
                raise ValueError("Conversation ID is required")
            if new_messages:
                async with AsyncPostgresSaver.from_conn_string(
                    settings.DATABASE_URL
                ) as checkpointer:
                    await checkpointer.setup()  # auto create tables in PostgresSql

                    # we don't need the answer, so we set a small max tokens
                    temp_max_tokens = self.model.max_tokens  # type: ignore[attr-defined]
                    self.model.max_tokens = 10  # type: ignore[attr-defined]
                    agent: CompiledStateGraph = create_agent(
                        model=self.model,
                        middleware=[self.get_summarizer(), remove_after_empty_message],
                        checkpointer=checkpointer,
                    )
                    # Add a blank human message to trigger summarization of the entire conversation history
                    result = await agent.ainvoke(
                        {
                            "messages": [
                                *new_messages,
                                HumanMessage(content="", id=EMPTY_MESSAGE_ID),
                            ],
                        },
                        config=self._get_agent_config_for_conversation(conversation_id),
                    )
                    self.model.max_tokens = temp_max_tokens  # type: ignore[attr-defined]
                    # Get the first message with summary flag from the result
                    summary_message = next(
                        (
                            message
                            for message in result["messages"]
                            if hasattr(message, "summary") and message.summary
                        ),
                        None,
                    )
                    if summary_message:
                        summary = summary_message.content
                    last_message_id = None
                    if new_messages:
                        try:
                            last_message_id = int(new_messages[-1].get("id", ""))
                        except Exception:
                            pass
                    if summary:
                        # Upsert the chat summary
                        self._upsert_chat_summary(
                            conversation_id=conversation_id,
                            summary=summary,
                            latest_message_id=last_message_id,
                        )
            return True, {
                "latest_summary": summary,
            }
        except Exception as exc:
            logger.exception("Failed to manage conversation")
            return False, {
                "message": str(exc),
            }

    async def _document_to_message(
        self,
        content: str,
        description: str,
        document_type: str,
    ) -> Dict[str, str]:
        """Convert a document's raw text to a message."""
        return {
            "role": "user",
            "content": f"""Here's a {document_type} file {description}: {content}""",
        }

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
        document_message = await self._document_to_message(
            content=content, description=description, document_type=document_type
        )

        try:
            success, response = await self._manage_conversation(
                conversation_id=conversation_id,
                new_messages=[document_message],
            )

            if not success:
                error_text = "unknown error"
                if "message" in response and isinstance(response["message"], str):
                    error_text = response["message"]
                logger.error("Failed to add document to chat summary conversation: %s", error_text)

        except Exception:
            logger.exception("Failed to add messages to chat summary")
            return

    def _upsert_chat_summary(
        self, conversation_id: int, summary: str, latest_message_id: int | None = None
    ) -> None:
        """Upsert the chat summary in the database."""
        try:
            # get the latest chat summary
            summary_row = self.db.get_chat_summary_by_conversation_id(conversation_id)
            if summary_row is not None:
                # update the summary
                self.db.update_chat_summary(
                    conversation_id=conversation_id,
                    new_summary=summary,
                    latest_message_id=latest_message_id or summary_row.latest_message_id,
                )
            else:
                # create a new chat summary
                self.db.create_chat_summary(
                    conversation_id=conversation_id,
                    summary=summary,
                    latest_message_id=latest_message_id or -1,
                )
        except Exception:
            logger.exception("Failed to upsert chat summary")

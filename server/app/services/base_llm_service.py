"""
Abstract base class for LLM services.

This module defines the common interface that all LLM services (OpenAI, Anthropic, etc.)
must implement to ensure consistent behavior across different providers.
"""

import re
from abc import ABC, abstractmethod
from datetime import datetime
from logging import getLogger
from typing import AsyncGenerator, List, NamedTuple, Optional

from pydantic import BaseModel, Field

from app.models import ChatMessageData
from app.models.llm_prompts import LLMModel
from app.services.chat_models import (
    StreamContentEvent,
    StreamConversationLockedEvent,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamIdeaUpdateEvent,
    StreamStatusEvent,
)

logger = getLogger(__name__)


class FileAttachmentData(NamedTuple):
    """File attachment data."""

    id: int
    chat_message_id: Optional[int]
    conversation_id: int
    filename: str
    file_size: int
    file_type: str
    s3_key: str
    created_at: datetime


class LLMIdeaGeneration(BaseModel):
    """LLM structured output model for idea generation."""

    title: str = Field(..., description="Generated idea title")
    short_hypothesis: str = Field(..., description="Generated short hypothesis")
    related_work: str = Field(..., description="Generated related work section")
    abstract: str = Field(..., description="Generated abstract")
    experiments: List[str] = Field(..., description="Generated list of experiments")
    expected_outcome: str = Field(..., description="Generated expected outcome")
    risk_factors_and_limitations: List[str] = Field(
        ..., description="Generated risk factors and limitations"
    )


class BaseLLMService(ABC):
    """
    Abstract base class for LLM services.

    All LLM service implementations must inherit from this class and implement
    the required methods to ensure a consistent interface across providers.
    """

    @abstractmethod
    def generate_idea(
        self, llm_model: str, conversation_text: str, user_id: int
    ) -> AsyncGenerator[str, None]:
        """
        Generate a research idea by streaming structured events.

        Args:
            llm_model: The LLM model to use for generation
            conversation_text: the conversation text to analyze
            user_id: the user id
            conversation_id: the conversation id

        Yields:
            str: JSON-encoded events. Partial events describe section updates,
                 and the final event includes the complete structured payload.

        Raises:
            Exception: If the LLM API call fails
        """
        pass

    @abstractmethod
    def _parse_idea_response(self, content: str) -> LLMIdeaGeneration:
        """
        Parse the idea response from the LLM.

        Args:
            content: The raw string content from the LLM

        Returns:
            LLMIdeaGeneration: Parsed idea with all fields

        Raises:
            ValueError: If the response format is invalid
        """
        pass

    @abstractmethod
    def chat_with_idea_stream(
        self,
        llm_model: LLMModel,
        conversation_id: int,
        idea_id: int,
        user_message: str,
        chat_history: List[ChatMessageData],
        attached_files: List[FileAttachmentData],
        user_id: int,
    ) -> AsyncGenerator[
        StreamContentEvent
        | StreamStatusEvent
        | StreamIdeaUpdateEvent
        | StreamConversationLockedEvent
        | StreamErrorEvent
        | StreamDoneEvent,
        None,
    ]:
        """
        Stream chat responses with idea context and tool calling.

        Args:
            llm_model: The LLM model to use
            conversation_id: ID of the conversation
            idea_id: ID of the idea
            user_message: User's message
            chat_history: Previous chat messages
            attached_files: List of FileAttachmentData objects
            user_id: ID of the user

        Yields:
            Stream events for the chat response

        Raises:
            Exception: If the LLM API call fails
        """
        pass

    @abstractmethod
    async def summarize_document(self, llm_model: LLMModel, content: str) -> str:
        """Generate a concise plain-text summary of the given content."""
        pass

    @abstractmethod
    async def summarize_image(self, llm_model: LLMModel, image_url: str) -> str:
        """Generate a detailed caption/description for an image at the given URL."""
        pass

    @abstractmethod
    async def generate_imported_chat_keywords(
        self, llm_model: str, imported_conversation_text: str
    ) -> str:
        """Generate imported chat keywords."""
        pass

    @abstractmethod
    def get_context_window_tokens(self, llm_model: str) -> int:
        """Get the context window tokens for a given model id from SUPPORTED_MODELS."""
        pass

    @abstractmethod
    async def generate_text_single_call(
        self,
        llm_model: str,
        system_prompt: str,
        user_prompt: str,
        max_completion_tokens: int,
    ) -> str:
        """
        Execute a single, non-streaming text generation call on the provider.

        Args:
            llm_model: Provider-specific model identifier
            system_prompt: System instruction to steer behavior
            user_prompt: User content to process
            max_completion_tokens: Upper bound for completion length

        Returns:
            Provider response text as a single string (may be empty on failure).
        """
        pass

    # Shared helpers
    @staticmethod
    def estimate_tokens_via_char_heuristic(text: str) -> int:
        """
        Estimate token count using a simple 4-chars-per-token heuristic.

        This is a fast approximation to guide budgeting. Providers may have
        different tokenization; use provider tokenizers for precision if needed.
        """
        return max(len(text) // 4, 0)

    @staticmethod
    def split_text_to_fit_char_budget(text: str, max_chars: int) -> List[str]:
        """
        Split text into chunks that each fit within a character budget.

        Prefers splitting on double-newlines when feasible to keep chunk
        boundaries semantically aligned; otherwise splits hard at the budget.
        Returns non-empty, trimmed chunks.
        """
        if max_chars <= 0 or len(text) <= max_chars:
            return [text]
        chunks: List[str] = []
        start_index = 0
        end = len(text)
        while start_index < end:
            candidate_end = min(end, start_index + max_chars)
            split_at = text.rfind("\n\n", start_index, candidate_end)
            if split_at == -1 or split_at < start_index + int(0.5 * max_chars):
                split_at = candidate_end
            chunks.append(text[start_index:split_at])
            start_index = split_at
        return [c for c in (s.strip() for s in chunks) if c]

    async def _generate_imported_chat_keywords(self, llm_model: str, conversation_text: str) -> str:
        """
        Extract 10–20 keywords using a map-reduce strategy under context limits.

        Splits the text to fit the model budget, extracts 5–10 keywords per
        chunk (map), merges and deduplicates, then reduces to a final set.
        """

        def parse_comma_separated_keywords_line(line: str) -> List[str]:
            """
            Parse a comma-separated keywords line into a list of normalized tokens.

            Normalizes whitespace and trims quotes. Ignores empty tokens.
            """
            cleaned = line.strip().replace("\n", " ")
            cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned)
            parts = [p.strip().strip("\"'") for p in cleaned.split(",")]
            return [p for p in parts if p]

        def dedupe_keywords_preserve_case_frequency(items: List[str]) -> List[str]:
            """
            Dedupe keywords case-insensitively while preserving original casing.

            Orders by descending frequency (case-insensitive) with stable order
            among equals, to keep more common terms first.
            """
            seen: dict[str, int] = {}
            ordered: List[str] = []
            for item in items:
                key = item.lower()
                if key not in seen:
                    seen[key] = 1
                    ordered.append(item)
                else:
                    seen[key] += 1
            ordered.sort(key=lambda v: -(seen[v.lower()]))
            return ordered

        system_prompt = (
            "You extract focused keywords. Return ONLY a single line of comma-separated keywords."
        )
        map_instruction = (
            "Extract 5-10 concise, specific keywords and key phrases from this chat excerpt. "
            "No explanatory text, no numbering, no quotes. Output a single line, comma-separated.\n\n"
        )
        reduce_instruction = (
            "From the following candidate keywords, choose the 10-20 most salient, "
            "deduplicate and normalize phrases. Return a single line, comma-separated.\n\n"
        )

        context_tokens = self.get_context_window_tokens(llm_model)
        map_completion_tokens = 600
        reduce_completion_tokens = 600
        overhead_tokens = 128
        sys_tokens = self.estimate_tokens_via_char_heuristic(system_prompt)
        map_inst_tokens = self.estimate_tokens_via_char_heuristic(map_instruction)
        available_for_map_text = max(
            context_tokens
            - (sys_tokens + map_inst_tokens + overhead_tokens + map_completion_tokens),
            0,
        )
        char_budget = max(available_for_map_text * 4, 0)

        text_chunks = self.split_text_to_fit_char_budget(
            text=conversation_text, max_chars=char_budget
        )
        candidate_keywords: List[str] = []
        for chunk in text_chunks:
            user_prompt = f"{map_instruction}Excerpt:\n\n{chunk}"
            piece = await self.generate_text_single_call(
                llm_model=llm_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_completion_tokens=map_completion_tokens,
            )
            candidate_keywords.extend(parse_comma_separated_keywords_line(piece))

        merged = dedupe_keywords_preserve_case_frequency(candidate_keywords)
        if len(merged) <= 20:
            return ", ".join(merged)

        max_reduce_candidates = 60
        reduce_input = ", ".join(merged[:max_reduce_candidates])
        reduce_user_prompt = f"{reduce_instruction}Candidates: {reduce_input}"
        reduced_text = await self.generate_text_single_call(
            llm_model=llm_model,
            system_prompt=system_prompt,
            user_prompt=reduce_user_prompt,
            max_completion_tokens=reduce_completion_tokens,
        )
        reduced_list = parse_comma_separated_keywords_line(reduced_text)
        reduced_list = dedupe_keywords_preserve_case_frequency(reduced_list)[:20]
        return ", ".join(reduced_list)

    async def _summarize_document(self, llm_model: LLMModel, content: str) -> str:
        """
        Summarize long content with map-reduce to respect model context limits.

        Splits input into budgeted chunks, summarizes each (map), then reduces
        into a cohesive final summary.
        """
        system_prompt = (
            "You are an expert summarizer. Provide a concise but information-dense summary "
            "covering main topics, entities, claims, and decisions."
        )
        map_instruction = (
            "Summarize this excerpt in 2-4 sentences focusing on key facts, decisions, and entities. "
            "No preamble, no lists.\n\n"
        )
        reduce_instruction = (
            "Combine these excerpt summaries into a single cohesive summary (4-8 sentences), "
            "remove redundancy, keep salient details. No preamble.\n\n"
        )

        model_id = llm_model.id
        context_tokens = self.get_context_window_tokens(model_id)
        map_completion_tokens = 600
        reduce_completion_tokens = 600
        overhead_tokens = 128
        sys_tokens = self.estimate_tokens_via_char_heuristic(system_prompt)
        map_inst_tokens = self.estimate_tokens_via_char_heuristic(map_instruction)
        available_for_map_text = max(
            context_tokens
            - (sys_tokens + map_inst_tokens + overhead_tokens + map_completion_tokens),
            0,
        )
        char_budget = max(available_for_map_text * 4, 0)

        text_chunks = self.split_text_to_fit_char_budget(text=content, max_chars=char_budget)
        chunk_summaries: List[str] = []
        for chunk in text_chunks:
            user_prompt = f"{map_instruction}{chunk}"
            piece = await self.generate_text_single_call(
                llm_model=model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_completion_tokens=map_completion_tokens,
            )
            chunk_summaries.append(piece.strip())

        # If single chunk, return directly
        if len(chunk_summaries) == 1:
            return chunk_summaries[0]

        reduce_input = "\n".join(f"- {s}" for s in chunk_summaries[:50])
        reduce_user_prompt = f"{reduce_instruction}{reduce_input}"
        final_summary = await self.generate_text_single_call(
            llm_model=model_id,
            system_prompt=system_prompt,
            user_prompt=reduce_user_prompt,
            max_completion_tokens=reduce_completion_tokens,
        )
        return final_summary.strip()

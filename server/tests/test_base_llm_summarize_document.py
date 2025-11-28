from typing import AsyncGenerator, List, Tuple

import pytest

from app.models import ChatMessageData, LLMModel
from app.services.base_llm_service import BaseLLMService, FileAttachmentData, LLMIdeaGeneration
from app.services.chat_models import (
    StreamContentEvent,
    StreamConversationLockedEvent,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamIdeaUpdateEvent,
    StreamStatusEvent,
)


class _StubService(BaseLLMService):
    def __init__(self, tokens: int) -> None:
        self._tokens = tokens
        self.calls: List[Tuple[str, str]] = []  # (kind, user_prompt)
        self.map_counter = 0

    # Abstracts not used in these tests
    def generate_idea(
        self, llm_model: str, conversation_text: str, user_id: int, conversation_id: int
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError

    def _parse_idea_response(self, content: str) -> LLMIdeaGeneration:
        del content
        return LLMIdeaGeneration(
            title="t",
            short_hypothesis="h",
            related_work="rw",
            abstract="a",
            experiments=["e1"],
            expected_outcome="o",
            risk_factors_and_limitations=["r"],
        )

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
        raise NotImplementedError

    async def summarize_document(self, llm_model: LLMModel, content: str) -> str:
        return await self._summarize_document(llm_model=llm_model, content=content)

    async def summarize_image(self, llm_model: LLMModel, image_url: str) -> str:
        del llm_model, image_url
        return ""

    async def generate_imported_chat_keywords(
        self, llm_model: str, imported_conversation_text: str
    ) -> str:
        del llm_model, imported_conversation_text
        return ""

    def get_context_window_tokens(self, llm_model: str) -> int:
        del llm_model
        return self._tokens

    async def generate_text_single_call(
        self,
        llm_model: str,
        system_prompt: str,
        user_prompt: str,
        max_completion_tokens: int,
    ) -> str:
        del llm_model, system_prompt, max_completion_tokens
        if "Combine these excerpt summaries" in user_prompt:
            self.calls.append(("reduce", user_prompt))
            return "FINAL"
        if "Summarize this excerpt" in user_prompt:
            self.map_counter += 1
            self.calls.append(("map", user_prompt))
            return f"MAP{self.map_counter}"
        self.calls.append(("other", user_prompt))
        return "OTHER"


def _llm_model(model_id: str) -> LLMModel:
    return LLMModel(
        id=model_id,
        provider="test",
        label=model_id,
        supports_images=False,
        supports_pdfs=False,
        context_window_tokens=10_000,
    )


@pytest.mark.asyncio
async def test__summarize_document_single_chunk_returns_map_summary() -> None:
    # Large token window to keep content in a single chunk
    svc = _StubService(tokens=50_000)
    model = _llm_model("m")

    out = await svc._summarize_document(llm_model=model, content="Short content.")

    assert out == "MAP1"
    kinds = [k for k, _ in svc.calls]
    assert kinds.count("map") == 1
    assert "reduce" not in kinds
    # Verify the map prompt contains the excerpt text
    map_prompts = [p for k, p in svc.calls if k == "map"]
    assert len(map_prompts) == 1
    assert "Summarize this excerpt" in map_prompts[0]
    assert "Short content." in map_prompts[0]


@pytest.mark.asyncio
async def test__summarize_document_multi_chunk_invokes_reduce_and_maps_multiple_times() -> None:
    # Small positive token window to force multiple chunks
    # With tokens ~820, available_for_map_text is small but > 0, leading to a small char budget
    svc = _StubService(tokens=820)
    model = _llm_model("m")

    long_text = "".join(["abcdefghij" * 10 for _ in range(5)])  # 500 chars

    out = await svc._summarize_document(llm_model=model, content=long_text)

    assert out == "FINAL"
    kinds = [k for k, _ in svc.calls]
    assert kinds.count("map") >= 2
    assert kinds[-1] == "reduce"
    # Verify map prompts and reduce prompt structure
    map_prompts = [p for k, p in svc.calls if k == "map"]
    assert all("Summarize this excerpt" in mp for mp in map_prompts)
    reduce_prompts = [p for k, p in svc.calls if k == "reduce"]
    assert len(reduce_prompts) == 1
    rp = reduce_prompts[0]
    assert "Combine these excerpt summaries" in rp
    # Since map returns MAP1, MAP2, ... the reduce input should reference them as bullet points
    assert "- MAP1" in rp
    assert "- MAP2" in rp


@pytest.mark.asyncio
async def test__summarize_document_zero_budget_falls_back_to_single_map() -> None:
    # With a very small token window, available_for_map_text <= 0 → char_budget 0 → single chunk
    svc = _StubService(tokens=100)
    model = _llm_model("m")

    long_text = "x" * 2000
    out = await svc._summarize_document(llm_model=model, content=long_text)

    assert out == "MAP1"
    kinds = [k for k, _ in svc.calls]
    assert kinds == ["map"]

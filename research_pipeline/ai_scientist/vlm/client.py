"""LangChain-based VLM wrapper for figure review."""

import base64
import io
import logging
from typing import Any, Tuple, cast
from uuid import UUID

from ae_paper_review import TokenUsage
from langchain.chat_models import init_chat_model
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from PIL import Image
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _usage_value_to_int(*, value: object) -> int:
    """Convert a usage metadata value to an integer."""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    try:
        return int(cast(Any, value))
    except Exception:
        return 0


class TrackCostCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that accumulates token usage."""

    def __init__(
        self,
        *,
        model: str,
        usage: TokenUsage,
    ) -> None:
        self.model = model
        self.usage = usage
        logger.debug("TrackCostCallbackHandler - model=%s", model)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: object,
    ) -> None:
        del run_id, parent_run_id, kwargs
        try:
            if not response.generations:
                logger.warning(
                    "LangChain response has no generations - cannot track tokens (model=%s)",
                    self.model,
                )
                return
            generation = response.generations[0]
            if not generation:
                logger.warning(
                    "LangChain response has empty generation list - cannot track tokens (model=%s)",
                    self.model,
                )
                return
            last_generation = generation[0]
            if not last_generation:
                logger.warning(
                    "LangChain generation is None - cannot track tokens (model=%s)",
                    self.model,
                )
                return
            if not isinstance(last_generation, ChatGeneration):
                logger.warning(
                    "LangChain generation is not ChatGeneration (type=%s) - cannot track tokens (model=%s)",
                    type(last_generation).__name__,
                    self.model,
                )
                return
            message = last_generation.message
            if not isinstance(message, AIMessage):
                logger.warning(
                    "LangChain message is not AIMessage (type=%s) - cannot track tokens (model=%s)",
                    type(message).__name__,
                    self.model,
                )
                return

            usage_metadata_raw = message.usage_metadata
            if not usage_metadata_raw:
                logger.warning(
                    "LangChain AIMessage has no usage_metadata - cannot track tokens (model=%s)",
                    self.model,
                )
                return

            usage_metadata: dict[str, object] = cast(dict[str, object], usage_metadata_raw)
            input_tokens = _usage_value_to_int(value=usage_metadata.get("input_tokens"))
            cached_input_tokens = _usage_value_to_int(
                value=usage_metadata.get("cached_input_tokens")
            )
            cache_write_input_tokens = _usage_value_to_int(
                value=usage_metadata.get("cache_creation_input_tokens")
            )
            output_tokens = _usage_value_to_int(value=usage_metadata.get("output_tokens"))

            if input_tokens == 0 and output_tokens == 0:
                logger.warning(
                    "LangChain returned zero tokens (model=%s) - possible tracking issue",
                    self.model,
                )

            parts = self.model.split(":", 1)
            provider = parts[0] if len(parts) == 2 else "unknown"

            logger.info(
                "LangChain token usage: input=%d, cached=%d, cache_write=%d, output=%d (model=%s)",
                input_tokens,
                cached_input_tokens,
                cache_write_input_tokens,
                output_tokens,
                self.model,
            )

            self.usage.add(
                provider=provider,
                model=self.model,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                cache_write_input_tokens=cache_write_input_tokens,
                output_tokens=output_tokens,
            )
        except Exception:
            logger.warning("Token tracking failed; continuing without tracking", exc_info=True)


def encode_image_to_base64(*, image_path: str) -> str:
    """Convert an image to base64 string."""
    with Image.open(image_path) as img_file:
        img = img_file.convert("RGB") if img_file.mode == "RGBA" else img_file.copy()
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        image_bytes = buffer.getvalue()
    return base64.b64encode(image_bytes).decode("utf-8")


def _build_vlm_messages(
    *,
    system_message: str,
    history: list[BaseMessage],
    msg: str,
    image_paths: list[str],
    max_images: int,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    if system_message:
        messages.append(SystemMessage(content=system_message))

    messages.extend(history)

    content_blocks: list[dict[str, Any]] = [{"type": "text", "text": msg}]
    for image_path in image_paths[:max_images]:
        base64_image = encode_image_to_base64(image_path=image_path)
        content_blocks.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                    "detail": "low",
                },
            }
        )
    messages.append(HumanMessage(content=content_blocks))  # type: ignore[arg-type]
    return messages


def _make_vlm_call(
    *,
    model: str,
    temperature: float,
    system_message: str,
    prompt: list[BaseMessage],
    usage: TokenUsage,
) -> AIMessage:
    history = prompt[:-1]
    last = prompt[-1] if prompt else HumanMessage(content="")
    user_content = last.content

    if isinstance(user_content, list):
        messages: list[BaseMessage] = []
        if system_message:
            messages.append(SystemMessage(content=system_message))
        messages.extend(history)
        messages.append(HumanMessage(content=user_content))
    else:
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=str(user_content)),
        ]

    chat = init_chat_model(model=model, temperature=temperature)
    retrying_chat = chat.with_retry(
        retry_if_exception_type=(Exception,),
        stop_after_attempt=3,
    )

    callbacks = [TrackCostCallbackHandler(model=model, usage=usage)]
    ai_message = retrying_chat.invoke(messages, config={"callbacks": callbacks})  # type: ignore[arg-type]
    return ai_message


def get_response_from_vlm(
    *,
    msg: str,
    image_paths: str | list[str],
    model: str,
    system_message: str,
    temperature: float,
    usage: TokenUsage,
    msg_history: list[BaseMessage] | None = None,
    max_images: int = 25,
) -> Tuple[str, list[BaseMessage]]:
    """Get response from vision-language model.

    Args:
        msg: The message to send
        image_paths: Path(s) to image file(s)
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        system_message: System message for the VLM
        temperature: Sampling temperature
        usage: Token usage accumulator
        msg_history: Optional message history
        max_images: Maximum number of images to include
    """
    if msg_history is None:
        msg_history = []

    paths_list = [image_paths] if isinstance(image_paths, str) else list(image_paths)
    messages = _build_vlm_messages(
        system_message=system_message,
        history=msg_history,
        msg=msg,
        image_paths=paths_list,
        max_images=max_images,
    )

    new_msg_history = msg_history + [messages[-1]]
    ai_message = _make_vlm_call(
        model=model,
        temperature=temperature,
        system_message=system_message,
        prompt=new_msg_history,
        usage=usage,
    )
    content_str = str(ai_message.content)
    full_history = new_msg_history + [ai_message]
    return content_str, full_history


def get_structured_response_from_vlm(
    *,
    msg: str,
    image_paths: str | list[str],
    model: str,
    system_message: str,
    temperature: float,
    schema_class: type[BaseModel],
    usage: TokenUsage,
    msg_history: list[BaseMessage] | None = None,
    max_images: int = 25,
) -> Tuple[BaseModel, list[BaseMessage]]:
    """Get structured response from vision-language model.

    Args:
        msg: The message to send
        image_paths: Path(s) to image file(s)
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        system_message: System message for the VLM
        temperature: Sampling temperature
        schema_class: Pydantic model class for structured output
        usage: Token usage accumulator
        msg_history: Optional message history
        max_images: Maximum number of images to include
    """
    if msg_history is None:
        msg_history = []

    paths_list = [image_paths] if isinstance(image_paths, str) else list(image_paths)
    messages = _build_vlm_messages(
        system_message=system_message,
        history=msg_history,
        msg=msg,
        image_paths=paths_list,
        max_images=max_images,
    )

    new_msg_history = msg_history + [messages[-1]]
    chat = init_chat_model(model=model, temperature=temperature)
    structured_chat = chat.with_structured_output(schema=schema_class)

    callbacks = [TrackCostCallbackHandler(model=model, usage=usage)]
    parsed = structured_chat.invoke(messages, config={"callbacks": callbacks})  # type: ignore[arg-type]

    if not isinstance(parsed, BaseModel):
        raise TypeError("Structured VLM response did not return a Pydantic model instance.")

    return parsed, new_msg_history

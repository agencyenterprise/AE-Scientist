import base64
import io
import logging
from typing import Any, Tuple

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from PIL import Image
from pydantic import BaseModel

from .llm import _create_chat_model
from .token_tracker import TrackCostCallbackHandler

logger = logging.getLogger("ai-scientist")


def encode_image_to_base64(image_path: str) -> str:
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
    # LangChain HumanMessage content supports multi-part content as a list
    messages.append(HumanMessage(content=content_blocks))  # type: ignore[arg-type]
    return messages


def get_structured_response_from_vlm(
    *,
    msg: str,
    image_paths: str | list[str],
    model: str,
    system_message: str,
    temperature: float,
    schema_class: type[BaseModel],
    print_debug: bool = False,
    msg_history: list[BaseMessage] | None = None,
    max_images: int = 25,
) -> Tuple[BaseModel, list[BaseMessage]]:
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
    chat = _create_chat_model(model=model, temperature=temperature)
    structured_chat = chat.with_structured_output(schema=schema_class)
    parsed = structured_chat.invoke(
        messages, config={"callbacks": [TrackCostCallbackHandler(model)]}
    )
    if not isinstance(parsed, BaseModel):
        raise TypeError("Structured VLM response did not return a Pydantic model instance.")

    if print_debug:
        logger.debug("")
        logger.debug("%s VLM STRUCTURED START %s", "*" * 20, "*" * 20)
        logger.debug(parsed.model_dump_json(indent=2))
        logger.debug("%s VLM STRUCTURED END %s", "*" * 21, "*" * 21)
        logger.debug("")

    return parsed, new_msg_history

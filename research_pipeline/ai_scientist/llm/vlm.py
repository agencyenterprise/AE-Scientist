import base64
import io
import json
import logging
import re
from typing import Any, Tuple

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from PIL import Image

from .token_tracker import track_token_usage

logger = logging.getLogger("ai-scientist")


def encode_image_to_base64(image_path: str) -> str:
    """Convert an image to base64 string."""
    with Image.open(image_path) as img:
        if img.mode == "RGBA":
            img = img.convert("RGB")
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


@track_token_usage
def make_vlm_call(
    model: str,
    temperature: float,
    system_message: str,
    prompt: list[BaseMessage],
) -> AIMessage:
    # In the VLM path, prompt already includes the image-bearing user message.
    # We rebuild LangChain messages from that history.
    history = prompt[:-1]
    last = prompt[-1] if prompt else HumanMessage(content="")
    user_content = getattr(last, "content", "")
    # user_content may already be a list of content blocks (text + image_url)
    if isinstance(user_content, list):
        messages: list[BaseMessage] = []
        if system_message:
            messages.append(SystemMessage(content=system_message))
        messages.extend(history)
        messages.append(HumanMessage(content=user_content))  # multi-part content
    else:
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=str(user_content)),
        ]
    logger.debug("VLM make_vlm_call - model=%s, temperature=%s", model, temperature)
    logger.debug("VLM make_vlm_call - system_message: %s", system_message)
    for idx, message in enumerate(messages):
        logger.debug(
            "VLM make_vlm_call - request message %s: %s - %s",
            idx,
            getattr(message, "type", type(message).__name__),
            getattr(message, "content", ""),
        )
    chat = init_chat_model(
        model=model,
        temperature=temperature,
    )
    retrying_chat = chat.with_retry(
        retry_if_exception_type=(Exception,),
        stop_after_attempt=3,
    )
    ai_message = retrying_chat.invoke(messages)
    logger.debug(
        "VLM make_vlm_call - response: %s - %s",
        getattr(ai_message, "type", type(ai_message).__name__),
        getattr(ai_message, "content", ""),
    )
    return ai_message


def get_response_from_vlm(
    msg: str,
    image_paths: str | list[str],
    model: str,
    system_message: str,
    temperature: float,
    print_debug: bool = False,
    msg_history: list[BaseMessage] | None = None,
    max_images: int = 25,
) -> Tuple[str, list[BaseMessage]]:
    """Get response from vision-language model."""
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

    # For LangChain-native history, we store the last user message as a HumanMessage.
    new_msg_history = msg_history + [messages[-1]]
    ai_message = make_vlm_call(
        model=model,
        temperature=temperature,
        system_message=system_message,
        prompt=new_msg_history,
    )
    content_str = str(ai_message.content)
    full_history = new_msg_history + [ai_message]

    if print_debug:
        logger.debug("%s", "")
        logger.debug("%s VLM START %s", "*" * 20, "*" * 20)
        for idx, message in enumerate(full_history):
            logger.debug(
                "%s, %s: %s",
                idx,
                getattr(message, "type", type(message).__name__),
                getattr(message, "content", ""),
            )
        logger.debug("%s", content_str)
        logger.debug("%s VLM END %s", "*" * 21, "*" * 21)
        logger.debug("%s", "")

    return content_str, full_history


def extract_json_between_markers_vlm(llm_output: str) -> dict[Any, Any] | None:
    # Regular expression pattern to find JSON content between ```json and ```
    json_pattern = r"```json(.*?)```"
    matches = re.findall(json_pattern, llm_output, re.DOTALL)

    if not matches:
        # Fallback: Try to find any JSON-like content in the output
        json_pattern = r"\{.*?\}"
        matches = re.findall(json_pattern, llm_output, re.DOTALL)

    for json_string in matches:
        json_string = json_string.strip()
        try:
            parsed_json: dict[Any, Any] | list[Any] = json.loads(json_string)
            if isinstance(parsed_json, dict):
                return parsed_json
        except json.JSONDecodeError:
            # Attempt to fix common JSON issues
            try:
                # Remove invalid control characters
                json_string_clean = re.sub(r"[\x00-\x1F\x7F]", "", json_string)
                parsed_json = json.loads(json_string_clean)
                if isinstance(parsed_json, dict):
                    return parsed_json
            except json.JSONDecodeError:
                continue  # Try next match

    return None  # No valid JSON found

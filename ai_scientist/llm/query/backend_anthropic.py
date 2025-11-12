import logging
import time
from typing import cast

import anthropic
from anthropic.types import Message as AnthropicMessage
from funcy import notnone, once, select_values  # type: ignore[import-untyped]

from .utils import FunctionSpec, OutputType, backoff_create, opt_messages_to_list

logger = logging.getLogger("ai-scientist")

_client: anthropic.Anthropic = None  # type: ignore
# _client: anthropic.AnthropicBedrock | None = None

ANTHROPIC_TIMEOUT_EXCEPTIONS = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
    anthropic.APIStatusError,
)


@once  # type: ignore[misc]
def _setup_anthropic_client() -> None:
    global _client
    _client = anthropic.Anthropic(max_retries=0)
    # _client = anthropic.AnthropicBedrock(max_retries=0)


def query(
    system_message: str | None,
    user_message: str | None,
    func_spec: FunctionSpec | None = None,
    **model_kwargs: object,
) -> tuple[OutputType, float, int, int, dict]:
    _setup_anthropic_client()

    filtered_kwargs: dict[str, object] = select_values(notnone, model_kwargs)
    if "max_tokens" not in filtered_kwargs:
        filtered_kwargs["max_tokens"] = 8192  # default for Claude models

    # Tool / function calling support for Anthropic (Claude tool use)
    if func_spec is not None:
        filtered_kwargs["tools"] = [
            {
                "name": func_spec.name,
                "description": func_spec.description,
                "input_schema": func_spec.json_schema,
            }
        ]
        # Force the model to produce a tool_use for this tool
        filtered_kwargs["tool_choice"] = {"type": "tool", "name": func_spec.name}

    if system_message is not None and user_message is None:
        system_message, user_message = user_message, system_message

    if system_message is not None:
        filtered_kwargs["system"] = system_message

    messages = opt_messages_to_list(None, user_message)

    logger.debug(f"Anthropic API request - messages: {messages}")
    logger.debug(f"Anthropic API request - kwargs: {filtered_kwargs}")

    t0 = time.time()
    message_any = backoff_create(
        create_fn=_client.messages.create,
        retry_exceptions=ANTHROPIC_TIMEOUT_EXCEPTIONS,
        messages=messages,
        **filtered_kwargs,
    )
    req_time = time.time() - t0

    if message_any is False:
        raise RuntimeError("Failed to create message after retries")

    message = cast(AnthropicMessage, message_any)

    logger.debug(f"Anthropic API response - content: {message.content}")
    logger.debug(
        f"Anthropic API response - usage: input_tokens={message.usage.input_tokens}, output_tokens={message.usage.output_tokens}"
    )
    logger.debug(f"Anthropic API response - stop_reason: {message.stop_reason}")

    # Parse output
    if func_spec is None:
        if "thinking" in filtered_kwargs:
            assert (
                len(message.content) == 2
                and message.content[0].type == "thinking"
                and message.content[1].type == "text"
            )
            output = cast(OutputType, getattr(message.content[1], "text"))
        else:
            assert len(message.content) >= 1
            # Find first text block
            first_text_block = next(
                (b for b in message.content if getattr(b, "type", None) == "text"),
                None,
            )
            assert first_text_block is not None and hasattr(
                first_text_block, "text"
            ), "No text content returned by Anthropic"
            output = getattr(first_text_block, "text")
    else:
        # Expect a tool_use block; extract its input as the structured output
        tool_uses = [b for b in message.content if getattr(b, "type", None) == "tool_use"]
        assert tool_uses, f"No tool_use returned by Anthropic for tool {func_spec.name}"
        tool_use = tool_uses[0]
        name = getattr(tool_use, "name", None)
        assert name == func_spec.name, "Function name mismatch"
        arguments = getattr(tool_use, "input", None)
        assert isinstance(arguments, dict), "Tool input must be an object"
        output = cast(OutputType, arguments)

    in_tokens = message.usage.input_tokens
    out_tokens = message.usage.output_tokens

    info = {
        "stop_reason": message.stop_reason,
    }

    logger.debug(f"Anthropic API response - parsed output: {output}")

    return output, req_time, in_tokens, out_tokens, info

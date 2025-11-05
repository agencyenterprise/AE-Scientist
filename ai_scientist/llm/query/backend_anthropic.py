import logging
import time
from typing import cast

import anthropic
from anthropic.types import Message as AnthropicMessage
from funcy import notnone, once, select_values  # type: ignore[import-untyped]

from .utils import FunctionSpec, OutputType, backoff_create, opt_messages_to_list

logger = logging.getLogger("ai-scientist")

# _client: anthropic.Anthropic = None  # type: ignore
_client: anthropic.AnthropicBedrock | None = None

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
    # _client = anthropic.Anthropic(max_retries=0)
    _client = anthropic.AnthropicBedrock(max_retries=0)


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

    if func_spec is not None:
        raise NotImplementedError("Anthropic does not support function calling for now.")

    if system_message is not None and user_message is None:
        system_message, user_message = user_message, system_message

    if system_message is not None:
        filtered_kwargs["system"] = system_message

    messages = opt_messages_to_list(None, user_message)

    t0 = time.time()
    message_any = backoff_create(
        create_fn=_client.messages.create,  # type: ignore[union-attr]
        retry_exceptions=ANTHROPIC_TIMEOUT_EXCEPTIONS,
        messages=messages,
        **filtered_kwargs,
    )
    req_time = time.time() - t0
    logger.debug(f"Anthropic API call kwargs: {filtered_kwargs}")

    if message_any is False:
        raise RuntimeError("Failed to create message after retries")

    message = cast(AnthropicMessage, message_any)

    if "thinking" in filtered_kwargs:
        assert (
            len(message.content) == 2
            and message.content[0].type == "thinking"
            and message.content[1].type == "text"
        )
        output_text = message.content[1].text
    else:
        assert len(message.content) == 1 and message.content[0].type == "text"
        output_text = message.content[0].text

    in_tokens = message.usage.input_tokens
    out_tokens = message.usage.output_tokens

    info = {
        "stop_reason": message.stop_reason,
    }

    return output_text, req_time, in_tokens, out_tokens, info

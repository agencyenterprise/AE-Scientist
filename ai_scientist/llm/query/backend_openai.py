import json
import logging
import time
from typing import cast

import openai
from funcy import notnone, once, select_values  # type: ignore[import-untyped]
from openai.types.chat import ChatCompletion

from .utils import (
    FunctionSpec,
    OutputType,
    backoff_create,
    get_openai_base_url,
    opt_messages_to_list,
)

logger = logging.getLogger("ai-scientist")

_client: openai.OpenAI | None = None

OPENAI_TIMEOUT_EXCEPTIONS = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)


@once  # type: ignore[misc]
def _setup_openai_client() -> None:
    global _client
    base_url = get_openai_base_url()
    if base_url:
        logger.info(f"Using custom OpenAI base_url: {base_url}")
    _client = openai.OpenAI(max_retries=0, base_url=base_url)


def query(
    system_message: str | None,
    user_message: str | None,
    func_spec: FunctionSpec | None = None,
    **model_kwargs: object,
) -> tuple[OutputType, float, int, int, dict]:
    _setup_openai_client()
    filtered_kwargs: dict[str, object] = select_values(notnone, model_kwargs)

    model_val = filtered_kwargs.get("model")
    if isinstance(model_val, str) and "gpt-5" in model_val and "temperature" in filtered_kwargs:
        filtered_kwargs["temperature"] = 1.0

    messages = opt_messages_to_list(system_message, user_message)

    if func_spec is not None:
        filtered_kwargs["tools"] = [func_spec.as_openai_tool_dict]
        filtered_kwargs["tool_choice"] = func_spec.openai_tool_choice_dict

    t0 = time.time()
    completion_any = backoff_create(
        create_fn=_client.chat.completions.create,  # type: ignore[union-attr]
        retry_exceptions=OPENAI_TIMEOUT_EXCEPTIONS,
        messages=messages,
        **filtered_kwargs,
    )
    req_time = time.time() - t0

    if completion_any is False:
        raise RuntimeError("Failed to create completion after retries")

    completion = cast(ChatCompletion, completion_any)

    choice = completion.choices[0]

    if func_spec is None:
        output = choice.message.content or ""
    else:
        assert (
            choice.message.tool_calls
        ), f"function_call is empty, it is not a function call: {choice.message}"
        tool_call = choice.message.tool_calls[0]
        func = getattr(tool_call, "function", None)
        assert (
            func is not None and getattr(func, "name", None) == func_spec.name
        ), "Function name mismatch"
        try:
            logger.debug(f"Raw func call response: {choice}")
            output = json.loads(func.arguments)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding the function arguments: {getattr(func, 'arguments', '')}")
            raise e

    in_tokens = completion.usage.prompt_tokens if completion.usage is not None else 0
    out_tokens = completion.usage.completion_tokens if completion.usage is not None else 0

    info: dict[str, object] = {
        "system_fingerprint": completion.system_fingerprint,
        "model": completion.model,
        "created": completion.created,
    }

    return cast(OutputType, output), req_time, in_tokens, out_tokens, cast(dict, info)

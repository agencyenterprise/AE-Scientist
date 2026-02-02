"""LLM wrapper functions for paper review."""

import json
import logging
from typing import Any, Tuple

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from .token_tracking import TokenUsage, TrackCostCallbackHandler

logger = logging.getLogger(__name__)


def _create_chat_model(provider: str, model: str, temperature: float) -> BaseChatModel:
    """Create a chat model using separate provider and model parameters.

    LangChain's init_chat_model expects 'provider:model' format (with colon).
    We combine provider and model with a colon separator.

    Args:
        provider: LLM provider (e.g., "anthropic", "openai")
        model: Model name (e.g., "claude-sonnet-4-20250514")
        temperature: Sampling temperature

    Returns:
        Configured BaseChatModel instance
    """
    model_string = f"{provider}:{model}"
    return init_chat_model(
        model=model_string,
        temperature=temperature,
    )


PromptType = str | dict[str, Any] | list[Any] | None


def get_batch_responses_from_llm(
    prompt: str,
    provider: str,
    model: str,
    system_message: str,
    temperature: float,
    print_debug: bool = True,
    msg_history: list[BaseMessage] | None = None,
    n_responses: int = 1,
    usage: TokenUsage | None = None,
) -> tuple[list[str], list[list[BaseMessage]]]:
    """Get multiple responses from an LLM."""
    if msg_history is None:
        msg_history = []

    contents: list[str] = []
    histories: list[list[BaseMessage]] = []
    for _ in range(n_responses):
        content, history = get_response_from_llm(
            prompt=prompt,
            provider=provider,
            model=model,
            system_message=system_message,
            temperature=temperature,
            print_debug=print_debug,
            msg_history=msg_history,
            usage=usage,
        )
        contents.append(content)
        histories.append(history)

    return contents, histories


def make_llm_call(
    provider: str,
    model: str,
    temperature: float,
    system_message: str,
    prompt: list[BaseMessage],
    usage: TokenUsage | None = None,
) -> AIMessage:
    """Make a single LLM call with optional token tracking."""
    messages: list[BaseMessage] = []
    if system_message:
        messages.append(SystemMessage(content=system_message))
    messages.extend(prompt)

    logger.debug(
        "LLM make_llm_call - provider=%s, model=%s, temperature=%s", provider, model, temperature
    )
    logger.debug("LLM make_llm_call - system_message: %s", system_message)
    for idx, message in enumerate(messages):
        logger.debug(
            "LLM make_llm_call - request message %s: %s - %s",
            idx,
            message.type,
            message.content,
        )

    chat = _create_chat_model(provider=provider, model=model, temperature=temperature)
    retrying_chat = chat.with_retry(
        retry_if_exception_type=(Exception,),
        stop_after_attempt=3,
    )

    callbacks = [TrackCostCallbackHandler(provider=provider, model=model, usage=usage)]
    ai_message = retrying_chat.invoke(
        messages, config={"callbacks": callbacks}  # type: ignore[arg-type]
    )

    logger.debug(
        "LLM make_llm_call - response: %s - %s",
        ai_message.type,
        ai_message.content,
    )
    return ai_message


def get_response_from_llm(
    prompt: str,
    provider: str,
    model: str,
    system_message: str,
    temperature: float,
    print_debug: bool = True,
    msg_history: list[BaseMessage] | None = None,
    usage: TokenUsage | None = None,
) -> Tuple[str, list[BaseMessage]]:
    """Get a response from an LLM."""
    if msg_history is None:
        msg_history = []

    new_msg_history = msg_history + [HumanMessage(content=prompt)]
    ai_message = make_llm_call(
        provider=provider,
        model=model,
        temperature=temperature,
        system_message=system_message,
        prompt=new_msg_history,
        usage=usage,
    )
    content = str(ai_message.content)
    full_history = new_msg_history + [ai_message]

    if print_debug:
        logger.debug("%s", "")
        logger.debug("%s", "*" * 20 + " LLM START " + "*" * 20)
        for idx, message in enumerate(full_history):
            logger.debug("%s, %s: %s", idx, message.type, message.content)
        logger.debug("%s", content)
        logger.debug("%s", "*" * 21 + " LLM END " + "*" * 21)
        logger.debug("%s", "")

    return content, full_history


def compile_prompt_to_md(
    prompt: object,
    _header_depth: int = 1,
) -> str | list[Any] | dict[str, Any]:
    """Compile a prompt object to markdown format."""
    try:
        if prompt is None:
            return ""

        if isinstance(prompt, str):
            return prompt.strip() + "\n"

        if isinstance(prompt, (int, float, bool)):
            return str(prompt).strip() + "\n"

        if isinstance(prompt, list):
            if not prompt:
                return ""
            if all(isinstance(item, dict) and "type" in item for item in prompt):
                return prompt

            try:
                result = "\n".join([f"- {str(s).strip()}" for s in prompt] + ["\n"])
                return result
            except Exception:
                logger.exception("Error processing list items")
                raise

        if isinstance(prompt, dict):
            if "type" in prompt:
                return prompt

            try:
                out: list[str] = []
                header_prefix = "#" * _header_depth
                for k, v in prompt.items():
                    out.append(f"{header_prefix} {k}\n")
                    compiled_v = compile_prompt_to_md(
                        prompt=v,
                        _header_depth=_header_depth + 1,
                    )
                    if isinstance(compiled_v, str):
                        out.append(compiled_v)
                    else:
                        out.append(str(compiled_v))
                return "\n".join(out)
            except Exception:
                logger.exception("Error processing dict")
                raise

        raise ValueError(f"Unsupported prompt type: {type(prompt)}")

    except Exception as exc:
        logger.exception("Error in compile_prompt_to_md:")
        logger.error("Input type: %s", type(prompt))
        logger.error("Error: %s", str(exc))
        raise


def get_structured_response_from_llm(
    *,
    prompt: str,
    provider: str,
    model: str,
    system_message: PromptType | None,
    temperature: float,
    schema_class: type[BaseModel],
    print_debug: bool = True,
    msg_history: list[BaseMessage] | None = None,
    usage: TokenUsage | None = None,
) -> Tuple[dict[str, Any], list[BaseMessage]]:
    """Get a structured response from an LLM using a Pydantic schema."""
    if msg_history is None:
        msg_history = []

    new_msg_history = msg_history + [HumanMessage(content=prompt)]

    combined_system = system_message
    messages: list[BaseMessage] = []
    if combined_system is not None:
        compiled_system = compile_prompt_to_md(prompt=combined_system)
        messages.append(SystemMessage(content=str(compiled_system)))
    messages.extend(new_msg_history)

    message_payload = [
        {
            "type": message.type,
            "content": message.content,
        }
        for message in messages
    ]
    logger.info(
        "LLM structured payload (provider=%s, model=%s, temperature=%s, messages=%s)",
        provider,
        model,
        temperature,
        len(message_payload),
    )
    logger.debug(
        "LLM structured payload detail: %s",
        json.dumps(message_payload, ensure_ascii=False),
    )

    chat = _create_chat_model(provider=provider, model=model, temperature=temperature)
    structured_chat = chat.with_structured_output(schema=schema_class)

    callbacks = [TrackCostCallbackHandler(provider=provider, model=model, usage=usage)]
    parsed_model = structured_chat.invoke(
        messages, config={"callbacks": callbacks}  # type: ignore[arg-type]
    )

    if not isinstance(parsed_model, BaseModel):
        raise TypeError("Structured output must be a Pydantic model instance.")

    parsed = parsed_model.model_dump(by_alias=True)
    ai_message = AIMessage(content=json.dumps(parsed))
    full_history = new_msg_history + [ai_message]

    if print_debug:
        logger.debug("")
        logger.debug("%s", "*" * 20 + " LLM STRUCTURED START " + "*" * 20)
        for idx, message in enumerate(full_history):
            logger.debug("%s, %s: %s", idx, message.type, message.content)
        logger.debug(json.dumps(parsed, indent=2))
        logger.debug("%s", "*" * 21 + " LLM STRUCTURED END " + "*" * 21)
        logger.debug("")

    return parsed, full_history

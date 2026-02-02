"""Research-pipeline specific structured LLM query functions.

These functions are specific to the tree search and experimentation workflows
and are not part of the shared ae-paper-review package.
"""

import logging
from typing import Any, TypeVar, cast

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel

from .llm import _create_chat_model
from .token_tracker import TrackCostCallbackHandler

logger = logging.getLogger("ai-scientist")


PromptType = str | dict[str, Any] | list[Any] | None
FunctionCallType = dict[str, Any]
OutputType = str | FunctionCallType
TStructured = TypeVar("TStructured", bound=BaseModel)


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


def _build_messages_for_query(
    *,
    system_message: PromptType | None,
    user_message: PromptType | None = None,
) -> list[BaseMessage]:
    """Build LangChain messages from system and user prompts."""
    messages: list[BaseMessage] = []
    if system_message is not None:
        compiled_system = compile_prompt_to_md(prompt=system_message)
        messages.append(SystemMessage(content=str(compiled_system)))
    if user_message is not None:
        compiled_user = compile_prompt_to_md(prompt=user_message)
        if isinstance(compiled_user, str):
            messages.append(HumanMessage(content=compiled_user))
        elif isinstance(compiled_user, list):
            normalized_blocks: list[str | dict[Any, Any]] = []
            for item in compiled_user:
                if isinstance(item, (str, dict)):
                    normalized_blocks.append(item)
                else:
                    normalized_blocks.append(str(item))
            messages.append(HumanMessage(content=normalized_blocks))
        elif isinstance(compiled_user, dict):
            messages.append(HumanMessage(content=[compiled_user]))
    return messages


def _invoke_langchain_query(
    *,
    system_message: PromptType | None,
    user_message: PromptType | None,
    model: str,
    temperature: float,
) -> str:
    """Invoke LangChain for a simple text query."""
    messages = _build_messages_for_query(
        system_message=system_message,
        user_message=user_message,
    )
    logger.debug("LLM _invoke_langchain_query - model=%s, temperature=%s", model, temperature)
    logger.debug("LLM _invoke_langchain_query - compiled messages:")
    for idx, message in enumerate(messages):
        logger.debug(
            "LLM _invoke_langchain_query - message %s: %s - %s",
            idx,
            message.type,
            message.content,
        )
    chat = _create_chat_model(model=model, temperature=temperature)
    ai_message = chat.invoke(messages, config={"callbacks": [TrackCostCallbackHandler(model)]})
    logger.debug(
        "LLM _invoke_langchain_query - response: %s - %s",
        ai_message.type,
        ai_message.content,
    )
    return str(ai_message.content)


def _invoke_structured_langchain_query(
    *,
    system_message: PromptType | None,
    user_message: PromptType | None,
    model: str,
    temperature: float,
) -> dict[str, Any]:
    """Invoke LangChain for a JSON-structured query."""
    messages = _build_messages_for_query(
        system_message=system_message,
        user_message=user_message,
    )
    logger.debug(
        "LLM _invoke_structured_langchain_query - model=%s, temperature=%s",
        model,
        temperature,
    )
    logger.debug("LLM _invoke_structured_langchain_query - compiled messages:")
    for idx, message in enumerate(messages):
        logger.debug(
            "LLM _invoke_structured_langchain_query - message %s: %s - %s",
            idx,
            message.type,
            message.content,
        )
    chat = _create_chat_model(model=model, temperature=temperature)
    retrying_chat = chat.with_retry(
        retry_if_exception_type=(Exception,),
        stop_after_attempt=3,
    )
    parser = JsonOutputParser()
    structured_chain = retrying_chat | parser
    parsed: dict[str, Any] = structured_chain.invoke(
        messages, config={"callbacks": [TrackCostCallbackHandler(model)]}
    )
    logger.debug("LLM _invoke_structured_langchain_query - parsed JSON: %s", parsed)
    return parsed


def structured_query_with_schema(
    *,
    system_message: PromptType | None,
    user_message: PromptType | None = None,
    model: str,
    temperature: float,
    schema_class: type[TStructured],
) -> TStructured:
    """
    Thin helper for structured outputs using a schema class.
    """
    messages = _build_messages_for_query(
        system_message=system_message,
        user_message=user_message,
    )
    chat = _create_chat_model(model=model, temperature=temperature)
    structured_chat = chat.with_structured_output(
        schema=schema_class,
    )
    result = structured_chat.invoke(
        input=messages,
        config={"callbacks": [TrackCostCallbackHandler(model)]},
    )
    return cast(TStructured, result)


def query(
    system_message: PromptType | None,
    user_message: PromptType | None,
    model: str,
    temperature: float,
) -> OutputType:
    """
    Unified LangChain-backed query interface for the tree search code.

    Returns the raw string output (or function-call dict) from the backing LLM.
    """
    return _invoke_langchain_query(
        system_message=system_message,
        user_message=user_message,
        model=model,
        temperature=temperature,
    )
